import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.api.parsers import iter_ozon_products, iter_wildberries_products, iter_yandex_market_products
from src.api.parsers.relevance_filter import filter_relevant
from src.api.parsers.spellcheck import spellcheck
from src.schemas import PriceSearchRequest, ProductPrice

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prices", tags=["Prices"], route_class=AutoDeriveResponsesAPIRoute)

NDJSON_MEDIA_TYPE = "application/x-ndjson"
STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}

YANDEX_SOURCE = "Yandex Market"
WILDBERRIES_SOURCE = "Wildberries"
OZON_SOURCE = "Ozon"


def _ndjson_line(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


@router.post("/search")
async def search_prices(payload: PriceSearchRequest) -> StreamingResponse:
    return StreamingResponse(
        _price_search_stream(payload),
        media_type=NDJSON_MEDIA_TYPE,
        headers=STREAM_HEADERS,
    )


async def _price_search_stream(payload: PriceSearchRequest) -> AsyncIterator[str]:
    request_started = time.perf_counter()
    source_timings: dict[str, float] = {}
    spellcheck_sec = 0.0

    logger.info(
        "Price search start: query=%r limit=%d skip=%d location=%r",
        payload.query,
        payload.limit,
        payload.skip,
        payload.location,
    )

    query = payload.query
    fixed_query: str | None = None
    if not payload.bypass_spellchecker:
        spell_started = time.perf_counter()
        query = await asyncio.to_thread(spellcheck, payload.query)
        spellcheck_sec = time.perf_counter() - spell_started
        if query != payload.query:
            fixed_query = query
        logger.info(
            "Price search spellcheck finished in %.2fs (query=%r -> %r)",
            spellcheck_sec,
            payload.query,
            query,
        )

    parsers_started = time.perf_counter()

    yield _ndjson_line(
        {
            "type": "meta",
            "query": payload.query,
            "fixed_query": fixed_query,
        },
    )

    queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()
    sources_done = 0

    async def pump_yandex() -> None:
        started = time.perf_counter()
        error: str | None = None
        try:
            async for batch in iter_yandex_market_products(
                query,
                payload.limit,
                payload.skip,
                location=payload.location,
            ):
                if not payload.bypass_relevance_filter:
                    batch = await filter_relevant(query, batch)
                prices = _products_from_raw(YANDEX_SOURCE, batch)
                if prices:
                    await queue.put(
                        (
                            "batch",
                            {"source": YANDEX_SOURCE, "prices": prices},
                        ),
                    )
            await queue.put(("source_done", {"source": YANDEX_SOURCE, "error": None}))
        except Exception as exc:
            error = str(exc)
            logger.exception("Yandex Market stream error for %r", query)
            await queue.put(
                ("source_done", {"source": YANDEX_SOURCE, "error": error}),
            )
        finally:
            elapsed = time.perf_counter() - started
            source_timings[YANDEX_SOURCE] = elapsed
            logger.info(
                "Price search %s finished in %.2fs (query=%r, error=%s)",
                YANDEX_SOURCE,
                elapsed,
                query,
                error or "none",
            )

    async def pump_wildberries() -> None:
        started = time.perf_counter()
        error: str | None = None
        try:
            async for batch in iter_wildberries_products(
                query,
                payload.limit,
                payload.skip,
                location=payload.location,
            ):
                if not payload.bypass_relevance_filter:
                    batch = await filter_relevant(query, batch)
                prices = _products_from_raw(WILDBERRIES_SOURCE, batch)
                if prices:
                    await queue.put(
                        (
                            "batch",
                            {"source": WILDBERRIES_SOURCE, "prices": prices},
                        ),
                    )
            await queue.put(("source_done", {"source": WILDBERRIES_SOURCE, "error": None}))
        except Exception as exc:
            error = str(exc)
            logger.exception("Wildberries stream error for %r", query)
            await queue.put(
                ("source_done", {"source": WILDBERRIES_SOURCE, "error": error}),
            )
        finally:
            elapsed = time.perf_counter() - started
            source_timings[WILDBERRIES_SOURCE] = elapsed
            logger.info(
                "Price search %s finished in %.2fs (query=%r, error=%s)",
                WILDBERRIES_SOURCE,
                elapsed,
                query,
                error or "none",
            )

    async def pump_ozon() -> None:
        started = time.perf_counter()
        error: str | None = None
        try:
            async for batch in iter_ozon_products(
                query,
                payload.limit,
                payload.skip,
                location=payload.location,
            ):
                if not payload.bypass_relevance_filter:
                    batch = await filter_relevant(query, batch)
                prices = _products_from_raw(OZON_SOURCE, batch)
                if prices:
                    await queue.put(
                        (
                            "batch",
                            {"source": OZON_SOURCE, "prices": prices},
                        ),
                    )
            await queue.put(("source_done", {"source": OZON_SOURCE, "error": None}))
        except Exception as exc:
            error = str(exc)
            logger.exception("Ozon stream error for %r", query)
            await queue.put(
                ("source_done", {"source": OZON_SOURCE, "error": error}),
            )
        finally:
            elapsed = time.perf_counter() - started
            source_timings[OZON_SOURCE] = elapsed
            logger.info(
                "Price search %s finished in %.2fs (query=%r, error=%s)",
                OZON_SOURCE,
                elapsed,
                query,
                error or "none",
            )

    tasks = [
        asyncio.create_task(pump_yandex()),
        asyncio.create_task(pump_wildberries()),
        asyncio.create_task(pump_ozon()),
    ]

    try:
        while sources_done < 3:
            event_type, data = await queue.get()
            yield _ndjson_line({"type": event_type, **data})
            if event_type == "source_done":
                sources_done += 1
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    yield _ndjson_line(
        {
            "type": "done",
            "query": payload.query,
            "fixed_query": fixed_query,
        },
    )

    parsers_sec = time.perf_counter() - parsers_started
    total_sec = time.perf_counter() - request_started
    logger.info(
        "Price search finished in %.2fs (query=%r): "
        "Yandex Market=%.2fs, Wildberries=%.2fs, Ozon=%.2fs, "
        "parsers_parallel=%.2fs, spellcheck=%.2fs",
        total_sec,
        payload.query,
        source_timings.get(YANDEX_SOURCE, 0.0),
        source_timings.get(WILDBERRIES_SOURCE, 0.0),
        source_timings.get(OZON_SOURCE, 0.0),
        parsers_sec,
        spellcheck_sec,
    )


def _products_from_raw(source: str, items: list[dict]) -> list[dict]:
    prices: list[dict] = []
    for item in items:
        sale_price = item.get("sale_price")
        if sale_price is None:
            continue
        prices.append(
            ProductPrice(
                source=source,
                name=item.get("name"),
                brand=_optional_brand(item.get("brand")),
                price=float(sale_price),
                original_price=_optional_float(item.get("original_price")),
                url=_optional_str(item.get("url")),
                image_url=_optional_str(item.get("image_url")),
            ).model_dump(mode="json"),
        )
    return prices


def _optional_brand(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() == "N/A":
        return None
    return text


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        first_string = next((item for item in value if isinstance(item, str)), None)
        return first_string
    return str(value)
