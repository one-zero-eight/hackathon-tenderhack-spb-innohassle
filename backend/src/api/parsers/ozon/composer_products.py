"""Map raw Ozon composer-api JSON to API product rows (backend-side parsing)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src.api.parsers.ozon.composer_extract import composer_listing_rows
from src.api.parsers.ozon.titles import pick_ozon_product_title
from src.api.parsers.price_utils import parse_rub_price


def count_priced_products_in_payload(payload: object) -> int:
    count = 0
    for row in composer_listing_rows(payload, limit=10_000):
        if parse_rub_price(row.get("price")) is not None:
            count += 1
    return count


def composer_listing_to_api_row(item: dict[str, Any]) -> dict[str, Any]:
    sale_price = parse_rub_price(item.get("price"))
    original_price = parse_rub_price(item.get("originalPrice"))
    title = pick_ozon_product_title(item.get("title")) or item.get("title") or "Без названия"
    return {
        "name": title,
        "brand": None,
        "sale_price": sale_price,
        "original_price": original_price,
        "url": item.get("url"),
        "image_url": item.get("image"),
        "source": "Ozon",
    }


def collect_products_from_composer_pages(
    pages: Iterable[dict[str, Any]],
    *,
    limit: int,
    skip: int = 0,
) -> list[dict[str, Any]]:
    """Merge composer pages, dedupe by URL, apply skip/limit."""
    target = skip + limit
    seen_urls: set[str] = set()
    collected: list[dict[str, Any]] = []

    sorted_pages = sorted(pages, key=lambda page: int(page.get("page") or 0))
    for page in sorted_pages:
        payload = page.get("data")
        if not isinstance(payload, dict):
            continue
        remaining = target - len(collected)
        if remaining <= 0:
            break
        for row in composer_listing_rows(payload, limit=remaining):
            url = row.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            api_row = composer_listing_to_api_row(row)
            if api_row.get("sale_price") is None:
                continue
            collected.append(api_row)
            if len(collected) >= target:
                break

    return collected[skip : skip + limit]
