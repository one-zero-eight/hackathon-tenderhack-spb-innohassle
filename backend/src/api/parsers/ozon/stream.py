from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from src.api.parsers.geocoder import resolve_ozon_city
from src.api.parsers.ozon.models import ProductResult
from src.api.parsers.ozon.parser import OzonParser
from src.api.parsers.ozon.titles import pick_ozon_product_title
from src.api.parsers.price_utils import parse_rub_price
from src.config import ozon_settings

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 10


def _listing_row_to_dict(item: dict) -> dict:
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


def _product_result_to_dict(product: object) -> dict:
    if not isinstance(product, ProductResult):
        raise TypeError(f"Expected ProductResult, got {type(product)}")
    sale_price = parse_rub_price(product.price)
    original_price = parse_rub_price(product.original_price)
    title = pick_ozon_product_title(product.title) or product.title or "Без названия"
    return {
        "name": title,
        "brand": product.brand,
        "sale_price": sale_price,
        "original_price": original_price,
        "url": product.url,
        "image_url": product.image_url,
        "source": "Ozon",
    }


async def iter_ozon_search(
    parser: OzonParser,
    query: str,
    limit: int,
    *,
    skip: int = 0,
    location: str | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> AsyncIterator[list[dict]]:
    fetch_details = ozon_settings.fetch_details
    detail_batch_size = max(1, (limit - 1) // 2) if limit > 1 else 1
    target_count = skip + limit

    logger.info(
        "Ozon stream start: query=%r limit=%d skip=%d location=%r fetch_details=%s",
        query,
        limit,
        skip,
        location,
        fetch_details,
    )

    if fetch_details:
        raw_results = await parser.run(
            query,
            limit,
            skip=skip,
            location=location,
            fetch_details=True,
            batch_size=detail_batch_size,
        )
        pending: list[dict] = []
        for product in raw_results[:limit]:
            pending.append(_product_result_to_dict(product))
            if len(pending) >= batch_size:
                yield pending
                pending = []
        if pending:
            yield pending
        return

    city = resolve_ozon_city(location)
    await parser._apply_delivery_city(city)
    await parser.search(query)

    skipped = 0
    emitted = 0
    pending: list[dict] = []

    async for listing_batch in parser.collect_products_batched(target_count, batch_size=batch_size):
        for item in listing_batch:
            if skipped < skip:
                skipped += 1
                continue
            row = _listing_row_to_dict(item)
            if row.get("sale_price") is None:
                continue
            pending.append(row)
            emitted += 1
            if len(pending) >= batch_size:
                yield pending
                pending = []
            if emitted >= limit:
                if pending:
                    yield pending
                return

    if pending:
        yield pending


async def iter_ozon_composer_raw(
    parser: OzonParser,
    query: str,
    limit: int,
    *,
    skip: int = 0,
    location: str | None = None,
) -> AsyncIterator[dict]:
    """Open Ozon SERP in browser, then yield composer-api pages until enough products (HTTP)."""
    if ozon_settings.fetch_details:
        raise ValueError("ozon composer_raw is incompatible with fetch_details")

    target = skip + limit
    logger.info(
        "Ozon composer raw stream: query=%r limit=%d skip=%d target=%d location=%r",
        query,
        limit,
        skip,
        target,
        location,
    )

    city = resolve_ozon_city(location)
    await parser._apply_delivery_city(city)
    await parser.search(query)

    async for page in parser.iter_composer_pages_until(target):
        yield page
