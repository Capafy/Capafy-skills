from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from typing import Any, Iterable, Mapping, Optional


STATE_FILENAME = "thin_skills_state.json"
LEGACY_STATE_DIRNAME = ".capafy"
RETAINED_ORDER_STATUSES = {"active", "expired"}


def skill_root_path(current_file: Optional[Path] = None) -> Path:
    base = Path(current_file) if current_file is not None else Path(__file__).resolve()
    return base.parents[1]


def state_file_path(skill_root: Optional[Path] = None) -> Path:
    root = skill_root if skill_root is not None else skill_root_path()
    return root / STATE_FILENAME


def legacy_state_file_path(skill_root: Optional[Path] = None) -> Path:
    root = skill_root if skill_root is not None else skill_root_path()
    return root / LEGACY_STATE_DIRNAME / STATE_FILENAME


def default_thin_skill_dir(agent_id: str, skill_root: Optional[Path] = None) -> str:
    resolved_agent_id = _string(agent_id)
    if not resolved_agent_id:
        raise ValueError("agent_id cannot be empty")
    root = skill_root if skill_root is not None else skill_root_path()
    return str((root.parent / f"capafy-agent-{resolved_agent_id}").resolve())


def _empty_state() -> dict[str, Any]:
    return {"agents": {}}


def load_state(skill_root: Optional[Path] = None) -> dict[str, Any]:
    path = state_file_path(skill_root)
    if not path.is_file():
        legacy_path = legacy_state_file_path(skill_root)
        if legacy_path.is_file():
            path = legacy_path
    if not path.is_file():
        return _empty_state()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid thin skill state json: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"thin skill state must be a JSON object: {path}")
    agents = payload.get("agents")
    if agents is None:
        payload["agents"] = {}
        return payload
    if not isinstance(agents, dict):
        raise ValueError(f"thin skill state 'agents' must be a JSON object: {path}")
    return payload


def get_agent_state(agent_id: str, skill_root: Optional[Path] = None) -> Optional[dict[str, Any]]:
    resolved_agent_id = _string(agent_id)
    if not resolved_agent_id:
        raise ValueError("agent_id cannot be empty")
    payload = load_state(skill_root)
    agent_state = payload["agents"].get(resolved_agent_id)
    if agent_state is None:
        return None
    if not isinstance(agent_state, dict):
        raise ValueError(f"invalid agent state entry for {resolved_agent_id}")
    return dict(agent_state)


def save_state(payload: Mapping[str, Any], skill_root: Optional[Path] = None) -> Path:
    path = state_file_path(skill_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    legacy_path = legacy_state_file_path(skill_root)
    if legacy_path != path and legacy_path.is_file():
        legacy_path.unlink(missing_ok=True)
        legacy_dir = legacy_path.parent
        try:
            legacy_dir.rmdir()
        except OSError:
            pass
    return path


def _utc_now(now: Optional[datetime] = None) -> str:
    resolved = now.astimezone(timezone.utc) if now is not None else datetime.now(timezone.utc)
    return resolved.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _string(value: object) -> str:
    return str(value or "").strip()


def _instance_name(item: Mapping[str, object], instance_id: str) -> str:
    return _string(item.get("instance_name")) or _string(item.get("name")) or instance_id


def _instance_status(item: Mapping[str, object]) -> str:
    return _string(item.get("order_status") or item.get("status")).lower()


def _normalize_instances(
    instances: Iterable[Mapping[str, object]],
    *,
    previous_last_used: Mapping[str, str],
    initialize_last_used_instance_id: Optional[str],
    now_iso: str,
) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in instances:
        instance_id = _string(item.get("instance_id") or item.get("instanceId"))
        if not instance_id or instance_id in seen:
            continue
        status = _instance_status(item)
        if status not in RETAINED_ORDER_STATUSES:
            continue
        entry = {
            "instance_id": instance_id,
            "instance_name": _instance_name(item, instance_id),
            "order_status": status,
        }
        last_used_at = _string(previous_last_used.get(instance_id))
        if not last_used_at and initialize_last_used_instance_id == instance_id:
            last_used_at = now_iso
        if last_used_at:
            entry["last_used_at"] = last_used_at
        normalized.append(entry)
        seen.add(instance_id)
    return normalized


def _find_instance(
    instances: Iterable[Mapping[str, str]],
    *,
    instance_id: Optional[str] = None,
) -> Optional[dict[str, str]]:
    target = _string(instance_id)
    if not target:
        return None
    for item in instances:
        if _string(item.get("instance_id")) == target:
            return dict(item)
    return None


def _choose_default_instance(
    instances: list[dict[str, str]],
    *,
    preferred_instance_id: Optional[str],
    previous_default_instance_id: Optional[str],
) -> Optional[dict[str, str]]:
    for candidate_id in (preferred_instance_id, previous_default_instance_id):
        selected = _find_instance(instances, instance_id=candidate_id)
        if selected is not None:
            return selected
    for status in ("active", "expired"):
        for item in instances:
            if item.get("order_status") == status:
                return item
    return instances[0] if instances else None


def _safe_remove_thin_skill_dir(path_value: Optional[str], *, skill_root: Path) -> None:
    candidate = _string(path_value)
    if not candidate:
        return
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = (skill_root / path).resolve()
    else:
        path = path.resolve()
    protected = {
        skill_root.resolve(),
        skill_root.parent.resolve(),
        skill_root.parent.parent.resolve(),
        Path.home().resolve(),
    }
    if path in protected or str(path) in {"", "/", "."}:
        return
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def resolve_reuse_decision(
    agent_id: str,
    *,
    incoming_template_id: Optional[str] = None,
    skill_root: Optional[Path] = None,
) -> dict[str, Any]:
    resolved_agent_id = _string(agent_id)
    if not resolved_agent_id:
        raise ValueError("agent_id cannot be empty")

    agent_state = get_agent_state(resolved_agent_id, skill_root=skill_root)
    if agent_state is None:
        return {
            "status": "local_missing",
            "agent_id": resolved_agent_id,
            "source": "local_state",
        }

    instances = agent_state.get("instances")
    if not isinstance(instances, list) or not instances:
        return {
            "status": "local_missing",
            "agent_id": resolved_agent_id,
            "source": "local_state",
        }

    stored_template_id = _string(agent_state.get("thin_skill_template_id"))
    candidate_template_id = _string(incoming_template_id)
    payload: dict[str, Any] = {
        "status": "reuse_existing",
        "agent_id": resolved_agent_id,
        "source": "local_state",
        "default_instance_id": _string(agent_state.get("default_instance_id")),
        "default_instance_name": _string(agent_state.get("default_instance_name")),
        "default_order_status": _string(agent_state.get("default_order_status")),
        "instances": [dict(item) for item in instances if isinstance(item, dict)],
    }
    if stored_template_id:
        payload["thin_skill_template_id"] = stored_template_id

    if candidate_template_id and stored_template_id and candidate_template_id != stored_template_id:
        payload["status"] = "buyer_confirmation_required"
        payload["reason"] = "template_changed"
        payload["existing_template_id"] = stored_template_id
        payload["incoming_template_id"] = candidate_template_id
        payload["options"] = ["reuse_existing_instance", "create_new_instance"]

    return payload


def sync_agent_state(
    agent_id: str,
    *,
    instances: Iterable[Mapping[str, object]],
    default_instance_id: Optional[str] = None,
    thin_skill_template_id: Optional[str] = None,
    order_id: Optional[str] = None,
    thin_skill_dir: Optional[str] = None,
    initialize_last_used_instance_id: Optional[str] = None,
    skill_root: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> Optional[dict[str, Any]]:
    resolved_agent_id = _string(agent_id)
    if not resolved_agent_id:
        raise ValueError("agent_id cannot be empty")

    resolved_skill_root = skill_root if skill_root is not None else skill_root_path()
    payload = load_state(resolved_skill_root)
    agents = payload["agents"]
    existing = agents.get(resolved_agent_id)
    if existing is not None and not isinstance(existing, dict):
        raise ValueError(f"invalid agent state entry for {resolved_agent_id}")

    existing = dict(existing or {})
    previous_last_used = {
        _string(item.get("instance_id")): _string(item.get("last_used_at"))
        for item in existing.get("instances", [])
        if isinstance(item, dict)
    }
    now_iso = _utc_now(now)
    normalized_instances = _normalize_instances(
        instances,
        previous_last_used=previous_last_used,
        initialize_last_used_instance_id=_string(initialize_last_used_instance_id) or None,
        now_iso=now_iso,
    )
    if not normalized_instances:
        _safe_remove_thin_skill_dir(
            thin_skill_dir or _string(existing.get("thin_skill_dir")),
            skill_root=resolved_skill_root,
        )
        agents.pop(resolved_agent_id, None)
        save_state(payload, resolved_skill_root)
        return None

    default_instance = _choose_default_instance(
        normalized_instances,
        preferred_instance_id=default_instance_id,
        previous_default_instance_id=_string(existing.get("default_instance_id")) or None,
    )
    if default_instance is None:
        raise RuntimeError(f"no default instance available for {resolved_agent_id}")

    agent_state: dict[str, Any] = {
        "default_instance_id": default_instance["instance_id"],
        "default_instance_name": default_instance["instance_name"],
        "default_order_status": default_instance["order_status"],
        "instances": normalized_instances,
        "updated_at": now_iso,
    }

    resolved_template_id = _string(thin_skill_template_id) or _string(existing.get("thin_skill_template_id"))
    if resolved_template_id:
        agent_state["thin_skill_template_id"] = resolved_template_id
    resolved_order_id = _string(order_id) or _string(existing.get("order_id"))
    if resolved_order_id:
        agent_state["order_id"] = resolved_order_id
    resolved_thin_skill_dir = (
        _string(thin_skill_dir)
        or _string(existing.get("thin_skill_dir"))
        or default_thin_skill_dir(resolved_agent_id, resolved_skill_root)
    )
    if resolved_thin_skill_dir:
        agent_state["thin_skill_dir"] = resolved_thin_skill_dir

    agents[resolved_agent_id] = agent_state
    save_state(payload, resolved_skill_root)
    return agent_state


def update_template_id(
    agent_id: str,
    *,
    thin_skill_template_id: str,
    skill_root: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    resolved_agent_id = _string(agent_id)
    if not resolved_agent_id:
        raise ValueError("agent_id cannot be empty")
    resolved_template_id = _string(thin_skill_template_id)
    if not resolved_template_id:
        raise ValueError("thin_skill_template_id cannot be empty")

    resolved_skill_root = skill_root if skill_root is not None else skill_root_path()
    payload = load_state(resolved_skill_root)
    agents = payload["agents"]
    agent_state = agents.get(resolved_agent_id)
    if agent_state is None or not isinstance(agent_state, dict):
        return None

    agent_state["thin_skill_template_id"] = resolved_template_id
    agents[resolved_agent_id] = agent_state
    save_state(payload, resolved_skill_root)
    return dict(agent_state)


def mark_instance_used(
    instance_id: str,
    *,
    skill_root: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> Optional[dict[str, Any]]:
    resolved_instance_id = _string(instance_id)
    if not resolved_instance_id:
        raise ValueError("instance_id cannot be empty")

    resolved_skill_root = skill_root if skill_root is not None else skill_root_path()
    payload = load_state(resolved_skill_root)
    agents = payload["agents"]
    now_iso = _utc_now(now)

    for agent_id, agent_state in agents.items():
        if not isinstance(agent_state, dict):
            continue
        instances = agent_state.get("instances")
        if not isinstance(instances, list):
            continue
        for item in instances:
            if not isinstance(item, dict):
                continue
            if _string(item.get("instance_id")) != resolved_instance_id:
                continue
            item["last_used_at"] = now_iso
            agent_state["default_instance_id"] = resolved_instance_id
            agent_state["default_instance_name"] = _string(item.get("instance_name")) or resolved_instance_id
            agent_state["default_order_status"] = _string(item.get("order_status")).lower()
            agent_state["updated_at"] = now_iso
            agents[agent_id] = agent_state
            save_state(payload, resolved_skill_root)
            return agent_state
    return None


def _remove_agent(agent_id: str, skill_root: Optional[Path] = None) -> bool:
    """Remove a single agent entry and its thin-skill directory. Returns True if removed."""
    resolved_agent_id = _string(agent_id)
    if not resolved_agent_id:
        raise ValueError("agent_id cannot be empty")
    resolved_skill_root = skill_root if skill_root is not None else skill_root_path()
    payload = load_state(resolved_skill_root)
    agents = payload["agents"]
    existing = agents.pop(resolved_agent_id, None)
    if existing is None:
        return False
    if isinstance(existing, dict):
        _safe_remove_thin_skill_dir(
            _string(existing.get("thin_skill_dir")),
            skill_root=resolved_skill_root,
        )
    save_state(payload, resolved_skill_root)
    return True


def _main(argv: Optional[list[str]] = None) -> int:
    """CLI for diagnostics and manual repair.

    Subcommands:
      list                          Print full state as JSON
      get <agent_id>                Print a single agent's state as JSON (exit 1 if missing)
      resolve <agent_id>            Run resolve_reuse_decision and print result
      mark-used <instance_id>       Bump last_used_at, promote instance to default
      clear <agent_id>              Remove agent entry and its thin-skill directory
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Thin skill local state tool")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="dump the full thin_skills_state.json")

    p_get = sub.add_parser("get", help="print a single agent's state")
    p_get.add_argument("agent_id")

    p_resolve = sub.add_parser("resolve", help="run resolve_reuse_decision")
    p_resolve.add_argument("agent_id")
    p_resolve.add_argument("--incoming-template-id", dest="incoming_template_id", default=None)

    p_mark = sub.add_parser("mark-used", help="update last_used_at for an instance")
    p_mark.add_argument("instance_id")

    p_clear = sub.add_parser("clear", help="remove an agent entry (and its thin-skill dir)")
    p_clear.add_argument("agent_id")

    args = parser.parse_args(argv)

    try:
        if args.command == "list":
            print(json.dumps(load_state(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "get":
            state = get_agent_state(args.agent_id)
            if state is None:
                print(f"no state for agent_id={args.agent_id}", file=sys.stderr)
                return 1
            print(json.dumps(state, ensure_ascii=False, indent=2))
            return 0
        if args.command == "resolve":
            decision = resolve_reuse_decision(
                args.agent_id,
                incoming_template_id=args.incoming_template_id,
            )
            print(json.dumps(decision, ensure_ascii=False, indent=2))
            return 0
        if args.command == "mark-used":
            result = mark_instance_used(args.instance_id)
            if result is None:
                print(f"instance_id={args.instance_id} not found in local state", file=sys.stderr)
                return 1
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "clear":
            removed = _remove_agent(args.agent_id)
            print(json.dumps({"removed": removed, "agent_id": args.agent_id}))
            return 0 if removed else 1
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(_main())
