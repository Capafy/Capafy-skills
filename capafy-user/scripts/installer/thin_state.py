from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    from .. import thin_skill_state
except ImportError:  # pragma: no cover - install_package.py direct execution fallback
    import thin_skill_state  # type: ignore

from .source import (
    _fetch_agent_instances,
    _fetch_order_detail,
    _resolve_base_url,
)


def _derive_agent_id_from_folder(folder_name: Optional[str]) -> str:
    value = str(folder_name or "").strip()
    prefix = "capafy-agent-"
    if value.startswith(prefix):
        return value[len(prefix):]
    return ""


def sync_thin_skill_state_after_install(
    order_id: str,
    metadata: dict,
    installed_to: Path,
    *,
    base_url: str,
    access_token: Optional[str] = None,
) -> dict:
    """Best-effort Thin state sync after the package has been installed."""
    resolved_base_url = _resolve_base_url(base_url)

    # Order details are authoritative for agent/instance; folderName supplies an agent_id fallback only when details fail.
    try:
        order_detail = _fetch_order_detail(
            order_id,
            base_url=resolved_base_url,
            access_token=access_token,
        )
    except Exception as exc:  # pragma: no cover - defensive urllib boundary
        order_detail = {}
        detail_error = str(exc)
    else:
        detail_error = ""

    agent_id = order_detail.get("agent_id") or _derive_agent_id_from_folder(
        metadata.get("folder_name")
    )
    purchased_instance_id = order_detail.get("instance_id") or ""
    if not agent_id:
        return {
            "synced": False,
            "reason": "unable_to_determine_agent_id",
            "order_detail_error": detail_error,
        }

    instances, failed_statuses = _fetch_agent_instances(
        agent_id,
        base_url=resolved_base_url,
        access_token=access_token,
    )
    # A failed status query does not mean instances vanished; retain locally known instances for that status when replacing the snapshot.
    if failed_statuses:
        existing_state = thin_skill_state.get_agent_state(agent_id)
        existing_instances = (
            existing_state.get("instances", [])
            if isinstance(existing_state, dict)
            else []
        )
        known_ids = {
            str(item.get("instance_id") or "").strip() for item in instances
        }
        for item in existing_instances:
            if not isinstance(item, dict):
                continue
            if str(item.get("order_status") or "").lower() not in failed_statuses:
                continue
            instance_id = str(item.get("instance_id") or "").strip()
            if instance_id and instance_id not in known_ids:
                instances.append(dict(item))
                known_ids.add(instance_id)

    if not instances and purchased_instance_id:
        instances = [{
            "instance_id": purchased_instance_id,
            "instance_name": order_detail.get("agent_title") or purchased_instance_id,
            "order_status": "active",
        }]
    if not instances:
        return {
            "synced": False,
            "reason": "no_instances_found",
            "agent_id": agent_id,
        }

    try:
        agent_state = thin_skill_state.sync_agent_state(
            agent_id,
            instances=instances,
            default_instance_id=purchased_instance_id or None,
            thin_skill_template_id=metadata.get("thin_skill_template_id"),
            order_id=order_id,
            thin_skill_dir=str(installed_to),
            initialize_last_used_instance_id=purchased_instance_id or None,
        )
    except Exception as exc:  # pragma: no cover - state persistence boundary
        return {
            "synced": False,
            "reason": f"sync_agent_state_failed: {exc}",
            "agent_id": agent_id,
        }
    if agent_state is None:
        return {
            "synced": False,
            "reason": "sync_agent_state_returned_none",
            "agent_id": agent_id,
        }
    return {
        "synced": True,
        "agent_id": agent_id,
        "default_instance_id": agent_state.get("default_instance_id"),
        "default_instance_name": agent_state.get("default_instance_name"),
        "thin_skill_dir": agent_state.get("thin_skill_dir"),
        "instance_count": len(agent_state.get("instances") or []),
    }
