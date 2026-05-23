"""Merge raw search.wb.ru pages into API product rows (backend-side parsing)."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from src.api.parsers.wildberries.search_api import api_item_to_product, products_from_api_payload


def collect_products_from_search_pages(
    pages: Iterable[dict[str, Any]],
    *,
    limit: int,
    skip: int = 0,
) -> list[dict[str, Any]]:
    target = skip + limit
    seen_nm: set[int] = set()
    collected: list[dict[str, Any]] = []

    sorted_pages = sorted(pages, key=lambda page: int(page.get("page") or 0))
    for page in sorted_pages:
        payload = page.get("data")
        if not isinstance(payload, dict):
            continue
        if len(collected) >= target:
            break
        for item in products_from_api_payload(payload):
            try:
                nm_id = int(item.get("id"))
            except (TypeError, ValueError):
                continue
            if nm_id in seen_nm:
                continue
            product = api_item_to_product(item)
            if product is None:
                continue
            seen_nm.add(nm_id)
            collected.append(product)
            if len(collected) >= target:
                break

    return collected[skip : skip + limit]
