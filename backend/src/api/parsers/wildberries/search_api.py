"""Wildberries catalog search via search.wb.ru (in-browser fetch after SERP load)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from src.api.parsers.wait import safe_execute_script

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 10

WB_SEARCH_API = "https://search.wb.ru/exactmatch/ru/common/v18/search"
WB_PAGE_SIZE = 100


WB_FETCH_PAGE_JS = """
const query = arguments[0];
const dest = arguments[1];
const page = arguments[2];
const params = new URLSearchParams({
  appType: '1',
  curr: 'rub',
  dest: String(dest),
  lang: 'ru',
  page: String(page),
  query: query,
  resultset: 'catalog',
  sort: 'popular',
  spp: '30',
  suppressSpellcheck: 'false',
});
const url = 'https://search.wb.ru/exactmatch/ru/common/v18/search?' + params.toString();
return fetch(url, { credentials: 'include' })
  .then(async (response) => ({
    ok: response.ok,
    status: response.status,
    data: response.ok ? await response.json() : null,
  }))
  .catch((error) => ({ ok: false, status: 0, data: null, error: String(error) }));
"""


def _products_from_api_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    products = payload.get("products")
    if not isinstance(products, list):
        data = payload.get("data")
        if isinstance(data, dict):
            products = data.get("products")
    if not isinstance(products, list):
        return []
    return [item for item in products if isinstance(item, dict)]


def _rub_from_api_units(value: object) -> float | None:
    if value is None:
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if amount <= 0:
        return None
    # WB search API prices are usually in kopecks.
    if amount >= 1000:
        amount /= 100.0
    return amount


def _wb_image_url(nm_id: int) -> str | None:
    if nm_id <= 0:
        return None
    vol = nm_id // 100000
    part = nm_id // 1000
    basket = f"{(vol % 10) + 1:02d}"
    return f"https://basket-{basket}.wbbasket.ru/vol{vol}/part{part}/{nm_id}/images/c516x688/1.webp"


def api_item_to_product(item: dict[str, Any]) -> dict | None:
    nm = item.get("id")
    if nm is None:
        return None
    try:
        nm_id = int(nm)
    except (TypeError, ValueError):
        return None

    sale_price = _rub_from_api_units(item.get("salePriceU") or item.get("sale"))
    if sale_price is None:
        sale_price = _rub_from_api_units(item.get("priceU"))
    if sale_price is None:
        return None

    original_price = _rub_from_api_units(item.get("priceU"))
    if original_price is not None and abs(original_price - sale_price) < 0.01:
        original_price = None

    brand = item.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")

    return {
        "name": item.get("name"),
        "brand": str(brand).strip() if brand else None,
        "sale_price": sale_price,
        "original_price": original_price,
        "url": f"https://www.wildberries.ru/catalog/{nm_id}/detail.aspx",
        "image_url": _wb_image_url(nm_id),
        "source": "Wildberries",
    }


async def iter_products_via_browser_api(
    driver: object,
    keyword: str,
    limit: int,
    *,
    skip: int = 0,
    dest: int,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> AsyncIterator[list[dict]]:
    """Paginate search.wb.ru using the browser session (cookies, TLS)."""
    target = skip + limit
    max_pages = max(3, (target + WB_PAGE_SIZE - 1) // WB_PAGE_SIZE + 2)
    seen: set[int] = set()
    skipped_count = 0
    emitted = 0
    pending: list[dict] = []

    def drain(*, force: bool = False) -> list[list[dict]]:
        nonlocal pending
        batches: list[list[dict]] = []
        while len(pending) >= batch_size:
            batches.append(pending[:batch_size])
            pending = pending[batch_size:]
        if force and pending:
            batches.append(pending)
            pending = []
        return batches

    for page in range(1, max_pages + 1):
        raw = await safe_execute_script(driver, WB_FETCH_PAGE_JS, keyword, dest, page)
        if not isinstance(raw, dict) or not raw.get("ok"):
            status = raw.get("status") if isinstance(raw, dict) else "?"
            logger.warning("WB API page %d failed (status=%s)", page, status)
            break

        payload = raw.get("data")
        if not isinstance(payload, dict):
            break

        page_items = _products_from_api_payload(payload)
        if not page_items:
            break

        new_on_page = 0
        for item in page_items:
            nm = item.get("id")
            try:
                nm_id = int(nm)
            except (TypeError, ValueError):
                continue
            if nm_id in seen:
                continue
            seen.add(nm_id)

            product = api_item_to_product(item)
            if product is None:
                continue

            if skipped_count < skip:
                skipped_count += 1
                continue
            if emitted >= limit:
                for batch in drain(force=True):
                    yield batch
                return

            pending.append(product)
            emitted += 1
            new_on_page += 1
            for batch in drain():
                yield batch

        logger.info(
            "WB API page %d: +%d products (emitted=%d, target=%d)",
            page,
            new_on_page,
            emitted,
            limit,
        )

        if emitted >= limit:
            for batch in drain(force=True):
                yield batch
            return
        if new_on_page == 0:
            break

    for batch in drain(force=True):
        yield batch
