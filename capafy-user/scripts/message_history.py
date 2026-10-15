"""Read current-round V2 history as JSON pages without sending a new task."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Iterator, Optional
from urllib.parse import quote, urlencode

try:
    from . import capafy_http
except ImportError:  # pragma: no cover - CLI fallback
    import capafy_http  # type: ignore


class HistoryError(RuntimeError):
    def __init__(self, message: str, *, status: int = 0, response=None):
        super().__init__(message)
        self.status = status
        self.response = response


def iter_pages(
    instance_id: str,
    *,
    size: int = 100,
    cursor: Optional[str] = None,
    max_pages: int = 1000,
    platform_base_url: Optional[str] = None,
) -> Iterator[dict]:
    """Yield one server page at a time; errors leave earlier pages incomplete.

    Each invocation without a cursor starts a fresh time range. This helper
    preserves all events and does not infer task completion or deduplicate
    replayed history; the caller handles display and replay across invocations.
    """
    if not instance_id.strip():
        raise ValueError("instance_id must not be blank")
    if type(size) is not int or type(max_pages) is not int or max_pages < 1:
        raise ValueError("size must be an integer and max_pages must be positive")
    size = max(1, min(size, 200))
    path = f"/agent/relay/instances/v2/{quote(instance_id, safe='')}/messages"
    seen_cursors = {cursor} if cursor else set()
    expected_round = None
    for page_number in range(max_pages):
        params = {"size": size}
        if cursor:
            params["cursor"] = cursor
        body, status = capafy_http.request(
            "GET", f"{path}?{urlencode(params)}",
            auto_platform_auth=True, platform_base_url=platform_base_url,
        )
        if not 200 <= status < 300 or not isinstance(body, dict):
            raise HistoryError("History request failed; earlier pages are partial",
                               status=status, response=body)
        if "code" in body and body["code"] not in (0, "0"):
            raise HistoryError("History business error; earlier pages are partial",
                               status=status, response=body)
        required = {"messages", "activeMessageId", "size", "hasMore", "nextCursor", "snapshotAt"}
        if not required.issubset(body) or not isinstance(body["messages"], list):
            raise HistoryError("Invalid V2 history response", status=status, response=body)
        if (not all(isinstance(event, dict) for event in body["messages"])
                or type(body["hasMore"]) is not bool
                or type(body["size"]) is not int
                or body["size"] != len(body["messages"])):
            raise HistoryError("Invalid V2 history page fields", status=status, response=body)
        round_key = (body["activeMessageId"], body["snapshotAt"])
        if page_number and round_key != expected_round:
            raise HistoryError("History round or time range changed; restart without cursor",
                               status=status, response=body)
        expected_round = round_key
        next_cursor = body["nextCursor"]
        if body["hasMore"] and (
            not isinstance(next_cursor, str) or not next_cursor
            or next_cursor in seen_cursors
        ):
            raise HistoryError("Missing or repeated V2 cursor; history is incomplete",
                               status=status, response=body)
        yield body
        if not body["hasMore"]:
            return
        cursor = next_cursor
        seen_cursors.add(cursor)
    raise HistoryError("History page limit reached; resume with the last nextCursor")


def _main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance_id")
    parser.add_argument("--size", type=int, default=100)
    parser.add_argument("--cursor", help="Opaque nextCursor from a previous V2 page")
    parser.add_argument("--max-pages", type=int, default=1000)
    parser.add_argument("--base-url", dest="platform_base_url")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        for page in iter_pages(**vars(args)):
            print(json.dumps(page, ensure_ascii=False), flush=True)
    except (HistoryError, ValueError) as exc:
        error = {"error": "history_read_failed", "message": str(exc)}
        if isinstance(exc, HistoryError):
            error.update(http_status=exc.status, response=exc.response)
        print(json.dumps(error, ensure_ascii=False), flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main())
