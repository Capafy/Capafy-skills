from __future__ import annotations

import json
import sys


MAX_RESULTS = 5
MAX_SHORT_DESC = 150


def truncate(text: str, limit: int = MAX_SHORT_DESC) -> str:
    stripped = (text or "").strip()
    if len(stripped) <= limit:
        return stripped
    return stripped[: limit - 1].rstrip() + "…"


def first_billing(item: dict) -> dict:
    billings = item.get("billings")
    if not isinstance(billings, list):
        return {}
    for billing in billings:
        if isinstance(billing, dict):
            return billing
    return {}


def _price_value(billing: dict, *keys: str) -> str:
    for key in keys:
        value = billing.get(key)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return ""


def _money_label(amount: str, currency: object) -> str:
    normalized_currency = str(currency or "").strip().upper()
    if normalized_currency:
        return f"{normalized_currency} {amount}"
    return amount


def pricing_label(item: dict) -> str:
    billing = first_billing(item)
    billing_mode = str(
        item.get("billingMode")
        or billing.get("billingMode")
    ).lower()

    if billing_mode == "hourly":
        price = _price_value(billing, "hourlyPrice")
        price = _money_label(price, billing.get("currency")) if price else ""
        return f"{price} | Pay-per-Duration" if price else "Pay-per-Duration"
    if billing_mode == "subscription":
        price = _price_value(billing, "cyclePrice")
        price = _money_label(price, billing.get("currency")) if price else ""
        return f"{price} | Subscription" if price else "Subscription"
    if billing_mode == "download":
        price = _price_value(billing, "oneTimeFee")
        price = _money_label(price, billing.get("currency")) if price else ""
        return f"{price} | One-Time Purchase" if price else "One-Time Purchase"
    return "Pricing TBD"


def result_list(payload: dict) -> list[dict]:
    code = payload.get("code")
    if code != 0:
        raise ValueError(f"Search request failed: code={code}, msg={payload.get('msg', '')}")
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("list"), list):
        return [item for item in data["list"] if isinstance(item, dict)]
    raise ValueError("Search response is missing data.list; cannot determine search results")


def description_label(item: dict) -> str:
    card = item.get("agentCard")
    if not isinstance(card, dict):
        card = {}
    short_description = card.get("shortDescription")
    if str(short_description or "").strip():
        return truncate(str(short_description))
    tags = str(item.get("tags", "")).strip()
    if tags:
        return truncate(tags)
    return "No summary available"


def sales_label(item: dict) -> int:
    value = item.get("salesVolume", 0)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def rating_label(item: dict) -> str:
    value = item.get("rating")
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "?"
    if numeric > 5:
        numeric = numeric / 10
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.1f}".rstrip("0").rstrip(".")


def format_search_results(payload: dict) -> str:
    results = result_list(payload)
    results = results[:MAX_RESULTS]
    summary = f"🔍 Found {len(results)} matching agents on this page"
    lines = [summary, ""]

    for index, item in enumerate(results, start=1):
        title = str(item.get("title", "Untitled Agent")).strip()
        rating = rating_label(item)
        sales = sales_label(item)
        lines.append(f" {index}. {title}  ⭐{rating} ({sales} sales)")
        lines.append(f"    {description_label(item)}")
        lines.append(f"    {pricing_label(item)}")
        lines.append("")

    lines.append('Enter a number for details | enter "next page" to paginate | enter "use N" to start')
    return "\n".join(lines)


def _main() -> int:
    try:
        payload = json.load(sys.stdin)
        formatted = format_search_results(payload)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(formatted)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
