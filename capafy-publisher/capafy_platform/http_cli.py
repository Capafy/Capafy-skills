from __future__ import annotations


import json
import sys

from capafy_platform.http import _is_platform_request, normalize_platform_base_url, request


def _parse_header(s: str) -> tuple:
    k, _, v = s.partition(":")
    return k.strip(), v.strip()


def _main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Capafy HTTP tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("method", choices=["GET", "POST", "PATCH", "DELETE", "PUT"])
    parser.add_argument("url")
    json_input = parser.add_mutually_exclusive_group()
    json_input.add_argument("--json", dest="json_str", help="request body JSON string")
    json_input.add_argument("--json-stdin", action="store_true", help="read JSON from stdin to preserve quotes in Windows shells")
    parser.add_argument("--header", action="append", dest="headers", metavar="Key:Value")
    parser.add_argument("--out", dest="out_file", help="write response body to a file")
    parser.add_argument("--access-token", dest="access_token", help="explicitly set the platform access token; auto-injected only for platform hosts")
    parser.add_argument(
        "--no-auto-platform-token",
        action="store_true",
        help="disable local token auto-injection for platform hosts",
    )
    args = parser.parse_args()

    headers = {}
    if args.headers:
        for h in args.headers:
            k, v = _parse_header(h)
            headers[k] = v

    url = args.url
    platform_base_url = None
    if url.startswith("/"):
        platform_base_url = normalize_platform_base_url(None)
        url = f"{platform_base_url}{url}"

    json_body = None
    if args.json_stdin:
        raw_json = sys.stdin.read()
        if not raw_json.strip():
            parser.error("--json-stdin set but stdin was empty")
        try:
            json_body = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            parser.error(f"--json-stdin payload is not valid JSON: {exc}")
    elif args.json_str:
        try:
            json_body = json.loads(args.json_str)
        except json.JSONDecodeError as e:
            print(f"[http] failed to parse --json: {e}", file=sys.stderr)
            sys.exit(1)

    body, status = request(
        args.method,
        url,
        json_body=json_body,
        headers=headers,
        out_file=args.out_file,
        auto_platform_auth=not args.no_auto_platform_token,
        access_token=args.access_token,
        platform_base_url=platform_base_url,
    )

    if body is None:
        sys.exit(1)

    if args.out_file:
        print(f"[http] {status} written to {body}")
    elif isinstance(body, dict):
        print(json.dumps(body, ensure_ascii=False, indent=2))
    else:
        print(body)

    if status >= 400:
        sys.exit(1)
    if (
        _is_platform_request(url, platform_base_url=platform_base_url)
        and isinstance(body, dict)
        and "code" in body
        and body["code"] not in (0, "0")
    ):
        sys.exit(1)


if __name__ == "__main__":
    _main()
