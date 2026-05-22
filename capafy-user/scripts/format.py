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


def _price_value(item: dict, billing: dict, *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is None or str(value).strip() == "":
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
        or item.get("pricing_model", "")
    ).lower()
    if item.get("is_free") or billing_mode == "free":
        return "Free"

    generic_price = str(item.get("price", "")).strip()
    if billing_mode == "hourly":
        price = generic_price or _price_value(item, billing, "hourlyPrice")
        price = _money_label(price, billing.get("currency")) if price else ""
        return f"{price} | Pay-per-Duration" if price else "Pay-per-Duration"
    if billing_mode in {"subscription", "cycle"}:
        price = generic_price or _price_value(item, billing, "cyclePrice")
        price = _money_label(price, billing.get("currency")) if price else ""
        return f"{price} | Subscription" if price else "Subscription"
    if billing_mode == "download":
        price = generic_price or _price_value(item, billing, "oneTimeFee")
        price = _money_label(price, billing.get("currency")) if price else ""
        return f"{price} | One-Time Purchase" if price else "One-Time Purchase"
    if generic_price:
        return generic_price
    return "Pricing TBD"


def result_list(payload: dict) -> list[dict]:
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("list"), list):
        return [item for item in data["list"] if isinstance(item, dict)]
    results = payload.get("results")
    if isinstance(results, list):
        return [item for item in results if isinstance(item, dict)]
    return []


def result_total(payload: dict, results: list[dict]) -> int:
    total = payload.get("total")
    if isinstance(total, int):
        return total
    if isinstance(total, str) and total.isdigit():
        return int(total)
    return len(results)


def result_page(payload: dict) -> int:
    page = payload.get("page")
    if isinstance(page, int) and page > 0:
        return page
    if isinstance(page, str) and page.isdigit():
        return max(1, int(page))
    return 1


def description_label(item: dict) -> str:
    card = item.get("agentCard")
    if not isinstance(card, dict):
        card = {}
    for key in ("short_desc", "shortDesc", "summary", "shortDescription", "description"):
        value = item.get(key)
        if str(value or "").strip():
            return truncate(str(value))
    for key in ("short_desc", "shortDesc", "summary", "shortDescription", "description"):
        value = card.get(key)
        if str(value or "").strip():
            return truncate(str(value))
    tags = str(item.get("tags", "")).strip()
    if tags:
        return truncate(tags)
    category_name = str(item.get("categoryName", "")).strip()
    if category_name:
        return truncate(category_name)
    return "No summary available"


def sales_label(item: dict) -> int:
    value = item.get("sales")
    if value is None:
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


def is_free_item(item: dict) -> bool:
    billing_mode = str(item.get("billingMode") or item.get("pricing_model", "")).lower()
    return bool(item.get("is_free")) or billing_mode == "free"


def format_search_results(payload: dict) -> str:
    results = result_list(payload)
    total = result_total(payload, results)
    page = result_page(payload)
    results = results[:MAX_RESULTS]
    if results:
        start = (page - 1) * MAX_RESULTS + 1
        end = start + len(results) - 1
    else:
        start = 0
        end = 0
    lines = [f"🔍 Found {total} matching agents (showing {start}-{end or 0})", ""]

    for index, item in enumerate(results, start=1):
        title = str(item.get("title", "Untitled Agent")).strip()
        rating = rating_label(item)
        sales = sales_label(item)
        free_badge = " 🆓" if is_free_item(item) else ""
        lines.append(f" {index}. {title}{free_badge}  ⭐{rating} ({sales} sales)")
        lines.append(f"    {description_label(item)}")
        lines.append(f"    {pricing_label(item)}")
        lines.append("")

    lines.append('Enter a number for details | enter "next page" to paginate | enter "use N" to start')
    return "\n".join(lines)


def _main(argv: list[str] | None = None) -> int:
    del argv
    payload = json.load(sys.stdin)
    print(format_search_results(payload))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
