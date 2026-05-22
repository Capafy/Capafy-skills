from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

try:
    from . import auth, capafy_http, thin_skill_state
    from .defaults import DEFAULT_PLATFORM_BASE_URL
except ImportError:  # pragma: no cover - CLI fallback
    import auth, capafy_http, thin_skill_state  # type: ignore
    from defaults import DEFAULT_PLATFORM_BASE_URL  # type: ignore


TERMINAL_EVENT_TYPES = {"done", "timeout"}


def parse_event_stream(stream) -> tuple[list[dict], str | None]:
    events = list(iter_event_stream(stream))
    last_event_id = None
    if events:
        last_event_id = str(events[-1].get("event_id")) if events[-1].get("event_id") else None
    return events, last_event_id


def iter_event_stream(stream):
    lines: list[str] = []
    current_event_id: str | None = None

    for raw_line in stream:
        line = raw_line.decode(errors="replace").rstrip("\r\n")
        if line == "":
            event = _parse_event(lines, current_event_id)
            lines = []
            current_event_id = None
            if event is None:
                continue
            yield event
            continue
        if line.startswith("id:"):
            current_event_id = line[3:].strip()
            continue
        lines.append(line)

    if lines:
        event = _parse_event(lines, current_event_id)
        if event is not None:
            yield event


def _parse_event(lines: list[str], event_id: str | None) -> dict | None:
    data_parts = []
    for line in lines:
        if line.startswith("data:"):
            data_parts.append(line[5:].lstrip())
    if not data_parts:
        return None

    payload = "\n".join(data_parts)
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        event = {"type": "raw", "data": payload}

    if isinstance(event, dict) and event_id and "event_id" not in event:
        event["event_id"] = event_id
    return event if isinstance(event, dict) else {"type": "raw", "data": payload}


def build_messages_url(
    instance_id: str,
    *,
    base_url: str = DEFAULT_PLATFORM_BASE_URL,
    reconnect: bool = False,
) -> str:
    url = f"{base_url.rstrip('/')}/agent/relay/instances/{instance_id}/messages"
    if reconnect:
        url = f"{url}/reconnect"
    return url


def build_interrupt_url(instance_id: str, *, base_url: str = DEFAULT_PLATFORM_BASE_URL) -> str:
    return f"{base_url.rstrip('/')}/agent/relay/instances/{instance_id}/interrupt"


def _build_headers(token: str | None, *, has_json_body: bool) -> dict[str, str]:
    headers = {
        "Accept": "text/event-stream, application/json",
        "Cache-Control": "no-cache",
    }
    headers.update(capafy_http.platform_context_headers())
    if has_json_body:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _normalize_file_entry(entry) -> dict:
    """Normalize a file entry to ``{url, originalFileName}``.

    Accepts:
    - dict with at least ``url`` key (passed through)
    - plain URL string (``originalFileName`` derived from URL path)
    """
    if isinstance(entry, dict):
        return entry
    url = str(entry).strip()
    # Derive filename from the URL path, fallback to the full URL
    try:
        from urllib.parse import urlsplit
        path = urlsplit(url).path
        name = path.rsplit("/", 1)[-1] if path else url
    except Exception:
        name = url
    return {"url": url, "originalFileName": name or url}


def _normalize_files(files: list | None) -> list[dict] | None:
    if not files:
        return None
    return [_normalize_file_entry(f) for f in files]


def _build_message_request(
    instance_id: str,
    *,
    base_url: str,
    token: str | None,
    content: str | None,
    original_question: str | None,
    next_step_plan: str | None,
    files: list | None,
    reconnect: bool,
):
    body = None
    if not reconnect:
        payload: dict[str, object] = {"content": content or ""}
        if original_question:
            payload["originalQuestion"] = original_question
        if next_step_plan:
            payload["nextStepPlan"] = next_step_plan
        normalized_files = _normalize_files(files)
        if normalized_files:
            payload["files"] = normalized_files
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    return urllib.request.Request(
        build_messages_url(instance_id, base_url=base_url, reconnect=reconnect),
        data=body,
        headers=_build_headers(token, has_json_body=body is not None),
        method="POST",
    )


def _emit_event(event: dict) -> None:
    print(json.dumps(event, ensure_ascii=False))
    sys.stdout.flush()


def _header_value(headers, key: str) -> str:
    if headers is None:
        return ""
    target = key.strip().lower()
    if isinstance(headers, dict):
        for name, value in headers.items():
            if str(name).strip().lower() == target:
                return str(value)
        return ""
    getter = getattr(headers, "get", None)
    if getter is None:
        return ""
    value = getter(key)
    if value is None:
        value = getter(key.lower())
    return str(value or "")


def _is_event_stream_response(response) -> bool:
    content_type = _header_value(getattr(response, "headers", None), "Content-Type").lower()
    return "text/event-stream" in content_type


def _read_json_response(response) -> dict:
    raw = response.read()
    text = raw.decode(errors="replace").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"type": "raw", "data": text}
    if isinstance(payload, dict):
        return payload
    return {"type": "raw", "data": text}


def _read_http_error(exc: urllib.error.HTTPError) -> dict:
    raw = exc.read()
    text = raw.decode(errors="replace").strip()
    if not text:
        return {"status": exc.code, "error": exc.reason}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"status": exc.code, "error": text}
    if isinstance(payload, dict):
        return payload
    return {"status": exc.code, "error": text}


def _record_successful_send(instance_id: str, *, reconnect: bool) -> None:
    if reconnect:
        return
    try:
        thin_skill_state.mark_instance_used(instance_id)
    except (OSError, ValueError):
        return


def stream_message(
    instance_id: str,
    *,
    content: str | None = None,
    original_question: str | None = None,
    next_step_plan: str | None = None,
    next_step: str | None = None,
    files: list[dict] | list[str] | None = None,
    reconnect: bool = False,
    base_url: str = "",
    timeout: int = 300,
    max_retries: int = 3,
    auth_loader=None,
) -> int:
    if not base_url:
        base_url = capafy_http._normalize_platform_base_url()

    if not reconnect and content is None:
        raise ValueError("content is required unless reconnect=True")
    if next_step_plan is None and next_step is not None:
        next_step_plan = next_step

    token_loader = auth_loader or auth.load_token
    token = token_loader() if token_loader else None

    attempts = 0
    reconnect_mode = reconnect
    while attempts < max_retries:
        request = _build_message_request(
            instance_id,
            base_url=base_url,
            token=token,
            content=content,
            original_question=original_question,
            next_step_plan=next_step_plan,
            files=files,
            reconnect=reconnect_mode,
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if not _is_event_stream_response(response):
                    payload = _read_json_response(response)
                    _emit_event(payload)
                    _record_successful_send(instance_id, reconnect=reconnect_mode)
                    return 0
                saw_event = False
                for event in iter_event_stream(response):
                    saw_event = True
                    _emit_event(event)
                    if event.get("type") in TERMINAL_EVENT_TYPES:
                        _record_successful_send(instance_id, reconnect=reconnect_mode)
                        return 0

                attempts += 1
                reconnect_mode = True
                if not saw_event and attempts >= max_retries:
                    break
        except urllib.error.HTTPError as exc:
            _emit_event(_read_http_error(exc))
            return 1
        except (OSError, urllib.error.URLError):
            attempts += 1
            reconnect_mode = True

    _emit_event({"type": "error", "message": "SSE reconnect failed"})
    return 1


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="User Skill message SSE runner")
    parser.add_argument("instance_id")
    parser.add_argument("--content")
    parser.add_argument("--original-question")
    parser.add_argument("--next-step-plan")
    parser.add_argument("--next-step", dest="next_step_plan")
    parser.add_argument("--files", nargs="*", default=None, help="file URLs to send to Agent; each entry is auto-wrapped to {url, originalFileName}")
    parser.add_argument("--reconnect", action="store_true")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--max-retries", type=int, default=3)
    args = parser.parse_args(argv)

    if not args.reconnect and args.content is None:
        parser.error("--content is required unless --reconnect is set")

    return stream_message(
        args.instance_id,
        content=args.content,
        original_question=args.original_question,
        next_step_plan=args.next_step_plan,
        files=args.files,
        reconnect=args.reconnect,
        base_url=args.base_url,
        timeout=args.timeout,
        max_retries=args.max_retries,
    )


if __name__ == "__main__":
    sys.exit(_main())
