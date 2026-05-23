from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from extract_products import ParsedProduct, extract_products
from fastapi import APIRouter, FastAPI, Query
from fastapi.responses import StreamingResponse
from query_rewrite import rewrite_query
from yandex_search import (
    YandexCaptchaError,
    close_browser_session,
    init_browser_session,
    search_yandex,
)

NDJSON_MEDIA_TYPE = "application/x-ndjson"
API_PREFIX = "/search-api"


def _ndjson_line(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


def _aggregate_by_hostname(
    aggregated: dict[str, list[dict]],
    page_results: list[dict],
    *,
    extracted: bool,
) -> list[dict]:
    added: list[dict] = []
    for product in page_results:
        hostname = product.get("hostname")
        if not hostname:
            continue

        products = aggregated.setdefault(hostname, [])
        href = product.get("href")
        if href and any(existing.get("href") == href for existing in products):
            continue

        entry = {**product, "extracted": extracted}
        products.append(entry)
        added.append(entry)

    return added


def _aggregated_results(aggregated: dict[str, list[dict]]) -> list[dict]:
    return [
        {"hostname": hostname, "products": products}
        for hostname, products in sorted(aggregated.items())
    ]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_browser_session()
    yield
    await close_browser_session()


app = FastAPI(lifespan=lifespan)
router = APIRouter()


async def _yandex_search_stream(query: str, region: str) -> AsyncIterator[str]:
    rewritten_query = rewrite_query(query, region)
    yield _ndjson_line({
        "type": "meta",
        "query": query,
        "region": region,
        "rewritten_query": rewritten_query,
    })

    aggregated: dict[str, list[dict]] = {}
    try:
        async for page_results in search_yandex(query, region):
            _aggregate_by_hostname(aggregated, page_results, extracted=False)
            yield _ndjson_line({
                "type": "page",
                "results": _aggregated_results(aggregated),
            })
    except YandexCaptchaError as error:
        print(error)

    yield _ndjson_line({"type": "done"})


async def _yandex_extended_search_stream(query: str, region: str) -> AsyncIterator[str]:
    rewritten_query = rewrite_query(query, region)
    aggregated: dict[str, list[dict]] = {}
    aggregated_lock = asyncio.Lock()
    state_updates: asyncio.Queue[None] = asyncio.Queue()
    search_done = asyncio.Event()
    in_flight = 0
    in_flight_lock = asyncio.Lock()

    async def notify() -> None:
        await state_updates.put(None)

    async def current_results() -> list[dict]:
        async with aggregated_lock:
            return _aggregated_results(aggregated)

    async def add_yandex_page(page_results: list[dict]) -> list[dict]:
        async with aggregated_lock:
            added = _aggregate_by_hostname(aggregated, page_results, extracted=False)
        if added:
            await notify()
        return added

    async def apply_extraction(source: dict, parsed_products: list[ParsedProduct]) -> None:
        hostname = source["hostname"]
        href = source.get("href")

        async with aggregated_lock:
            products = aggregated.setdefault(hostname, [])
            aggregated[hostname] = [
                product
                for product in products
                if not (product.get("href") == href and product.get("extracted") is False)
            ]

            if parsed_products:
                for parsed in parsed_products:
                    aggregated[hostname].append({
                        "extracted": True,
                        "hostname": hostname,
                        "href": href,
                        **parsed.model_dump(),
                    })
            else:
                aggregated[hostname].append({**source, "extracted": True})

        await notify()

    async def extract_one(http_client: httpx.AsyncClient, source: dict) -> None:
        nonlocal in_flight
        async with in_flight_lock:
            in_flight += 1

        try:
            href = source.get("href")
            if not href:
                await apply_extraction(source, [])
                return

            parsed_products = await extract_products(http_client, href, query, region)
            await apply_extraction(source, parsed_products)
        except Exception as error:
            print(f"failed to extract {source.get('href')}: {error}")
            await apply_extraction(source, [])
        finally:
            async with in_flight_lock:
                in_flight -= 1
            await notify()

    async def run_search(http_client: httpx.AsyncClient) -> None:
        try:
            async for page_results in search_yandex(query, region):
                new_products = await add_yandex_page(page_results)
                for product in new_products:
                    asyncio.create_task(extract_one(http_client, product))
        except YandexCaptchaError as error:
            print(error)
        finally:
            search_done.set()
            await notify()

    yield _ndjson_line({
        "type": "meta",
        "query": query,
        "region": region,
        "rewritten_query": rewritten_query,
    })

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        search_task = asyncio.create_task(run_search(http_client))

        while True:
            await state_updates.get()
            payload: dict = {
                "type": "page",
                "results": await current_results(),
            }
            yield _ndjson_line(payload)

            async with in_flight_lock:
                finished = search_done.is_set() and in_flight == 0
            if finished:
                break

        await search_task

    yield _ndjson_line({"type": "done"})


@router.get("/yandex_search")
async def yandex_search(
    query: str = Query(..., min_length=1),
    region: str = Query("санкт-петербург", min_length=1),
):
    return StreamingResponse(
        _yandex_search_stream(query, region),
        media_type=NDJSON_MEDIA_TYPE,
    )


@router.get("/yandex_search_extended")
async def yandex_search_extended(
    query: str = Query(..., min_length=1),
    region: str = Query("санкт-петербург", min_length=1),
):
    return StreamingResponse(
        _yandex_extended_search_stream(query, region),
        media_type=NDJSON_MEDIA_TYPE,
    )


app.include_router(router, prefix=API_PREFIX)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=9005, reload=False)
