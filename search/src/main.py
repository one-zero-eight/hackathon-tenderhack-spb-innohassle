from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from extract_products import ParsedPageProducts, extract_products
from fastapi import FastAPI, Query
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
STREAM_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _ndjson_line(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False) + "\n"


def _summarize_results(results: list[dict]) -> tuple[int, int, int, int]:
    hostnames = len(results)
    products = 0
    extracted = 0
    non_extracted = 0

    for group in results:
        for product in group.get("products", []):
            products += 1
            if product.get("extracted"):
                extracted += 1
            else:
                non_extracted += 1

    return hostnames, products, extracted, non_extracted


def _print_progress(payload: dict) -> None:
    event_type = payload.get("type")

    if event_type == "meta":
        print(f"meta: query={payload.get('query')!r}", flush=True)
        return

    if event_type == "page":
        hostnames, products, extracted, non_extracted = _summarize_results(
            payload.get("results", []),
        )
        print(
            f"page: "
            f"hostnames={hostnames} "
            f"products={products} "
            f"extracted={extracted} "
            f"non_extracted={non_extracted}",
            flush=True,
        )
        return

    if event_type == "done":
        results = payload.get("results")
        if results:
            hostnames, products, extracted, non_extracted = _summarize_results(results)
            print(
                f"total: "
                f"hostnames={hostnames} "
                f"products={products} "
                f"extracted={extracted} "
                f"non_extracted={non_extracted}",
                flush=True,
            )
        print("done", flush=True)
        return

    print(f"{event_type}: {payload}", flush=True)


def _format_update(payload: dict) -> str:
    _print_progress(payload)
    return _ndjson_line(payload)


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


def _hostname_shop_fields(
    products: list[dict],
) -> tuple[str | None, str | None, str | None]:
    rating = None
    reviews = None
    delivery = None
    for product in products:
        if rating is None:
            rating = product.get("rating")
        if reviews is None:
            reviews = product.get("reviews")
        if delivery is None:
            delivery = product.get("delivery")
        if rating is not None and reviews is not None and delivery is not None:
            break
    return rating, reviews, delivery


def _hostname_group(hostname: str, products: list[dict]) -> dict:
    rating, reviews, delivery = _hostname_shop_fields(products)
    group: dict = {"hostname": hostname, "products": products}
    if rating is not None:
        group["rating"] = rating
    if reviews is not None:
        group["reviews"] = reviews
    if delivery is not None:
        group["delivery"] = delivery
    return group


def _aggregated_results(aggregated: dict[str, list[dict]]) -> list[dict]:
    return [
        _hostname_group(hostname, products)
        for hostname, products in sorted(aggregated.items())
    ]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_browser_session()
    yield
    await close_browser_session()


app = FastAPI(lifespan=lifespan, root_path=API_PREFIX)


def _parse_rating(value: object) -> float:
    if value is None:
        return 0.0
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return 0.0


def _product_price(product: dict) -> str | None:
    if product.get("extracted"):
        return product.get("cost")
    return product.get("price")


def _quality_product_count(products: list[dict]) -> int:
    return sum(
        1
        for product in products
        if _product_price(product) and product.get("thumbnail")
    )


def _shop_rating(group: dict) -> float:
    if group.get("rating") is not None:
        return _parse_rating(group["rating"])

    products = group.get("products", [])
    if not products:
        return 0.0
    return max(_parse_rating(product.get("rating")) for product in products)


def rerank_yandex_search(results: list[dict]) -> list[dict]:
    return sorted(
        results,
        key=lambda group: (
            -_quality_product_count(group.get("products", [])),
            -_shop_rating(group),
            group.get("hostname") or "",
        ),
    )


async def _yandex_search_stream(
    query: str,
    region: str,
    *,
    rerank: bool = False,
) -> AsyncIterator[str]:
    rewritten_query = rewrite_query(query, region)
    yield _format_update({
        "type": "meta",
        "query": query,
        "region": region,
        "rewritten_query": rewritten_query,
    })

    aggregated: dict[str, list[dict]] = {}
    try:
        async for page_results in search_yandex(query, region):
            _aggregate_by_hostname(aggregated, page_results, extracted=False)
            results = _aggregated_results(aggregated)
            if rerank:
                results = rerank_yandex_search(results)
            yield _format_update({
                "type": "page",
                "results": results,
            })
    except YandexCaptchaError as error:
        print(error)

    if rerank:
        final_results = rerank_yandex_search(_aggregated_results(aggregated))
        yield _format_update({"type": "done", "results": final_results})
    else:
        yield _format_update({"type": "done"})


async def _yandex_extended_search_stream(query: str, region: str) -> AsyncIterator[str]:
    rewritten_query = rewrite_query(query, region)
    aggregated: dict[str, list[dict]] = {}
    aggregated_lock = asyncio.Lock()
    state_updates: asyncio.Queue[None] = asyncio.Queue()
    search_done = asyncio.Event()
    in_flight = 0
    in_flight_lock = asyncio.Lock()
    extraction_tasks: set[asyncio.Task[None]] = set()
    search_task: asyncio.Task[None] | None = None

    async def notify() -> None:
        await state_updates.put(None)

    async def current_results() -> list[dict]:
        async with aggregated_lock:
            return _aggregated_results(aggregated)

    async def add_yandex_page(page_results: list[dict]) -> list[dict]:
        added: list[dict] = []
        for product in page_results:
            async with aggregated_lock:
                batch_added = _aggregate_by_hostname(aggregated, [product], extracted=False)
            if not batch_added:
                continue
            added.extend(batch_added)
            await notify()
        return added

    async def apply_extraction(source: dict, parsed_page: ParsedPageProducts) -> None:
        hostname = source["hostname"]
        href = source.get("href")

        async with aggregated_lock:
            products = aggregated.setdefault(hostname, [])
            aggregated[hostname] = [
                product
                for product in products
                if not (product.get("href") == href and product.get("extracted") is False)
            ]

        if parsed_page.products:
            for parsed in parsed_page.products:
                async with aggregated_lock:
                    aggregated[hostname].append({
                        "extracted": True,
                        "hostname": hostname,
                        "href": href,
                        **parsed.model_dump(),
                    })
                await notify()
            return

        async with aggregated_lock:
            if parsed_page.message:
                aggregated[hostname].append({
                    "extracted": True,
                    "hostname": hostname,
                    "href": href,
                    "message": parsed_page.message,
                })
            if not aggregated[hostname]:
                aggregated.pop(hostname, None)
        await notify()

    async def extract_one(source: dict) -> None:
        nonlocal in_flight

        try:
            href = source.get("href")
            if not href:
                await apply_extraction(source, ParsedPageProducts())
                return

            parsed_page = await extract_products(
                href,
                query,
                region,
                serp_price=source.get("price"),
                serp_thumbnail=source.get("thumbnail"),
            )
            await apply_extraction(source, parsed_page)
        except asyncio.CancelledError:
            raise
        except Exception:
            await apply_extraction(source, ParsedPageProducts())
        finally:
            async with in_flight_lock:
                in_flight -= 1
            await notify()

    async def schedule_extraction(source: dict) -> None:
        nonlocal in_flight

        async with in_flight_lock:
            in_flight += 1

        task = asyncio.create_task(extract_one(source))
        extraction_tasks.add(task)
        task.add_done_callback(extraction_tasks.discard)

    async def run_search() -> None:
        try:
            async for page_results in search_yandex(query, region):
                new_products = await add_yandex_page(page_results)
                for product in new_products:
                    await schedule_extraction(product)
        except asyncio.CancelledError:
            raise
        except YandexCaptchaError as error:
            print(error)
        finally:
            search_done.set()
            await notify()

    yield _format_update({
        "type": "meta",
        "query": query,
        "region": region,
        "rewritten_query": rewritten_query,
    })

    try:
        search_task = asyncio.create_task(run_search())

        while True:
            await state_updates.get()
            payload: dict = {
                "type": "page",
                "results": await current_results(),
            }
            yield _format_update(payload)

            async with in_flight_lock:
                finished = search_done.is_set() and in_flight == 0
            if finished and state_updates.empty():
                break

        await search_task
        if extraction_tasks:
            await asyncio.gather(*extraction_tasks, return_exceptions=True)
    finally:
        pending: list[asyncio.Task[None]] = []
        if search_task is not None and not search_task.done():
            search_task.cancel()
            pending.append(search_task)
        for task in list(extraction_tasks):
            if not task.done():
                task.cancel()
                pending.append(task)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

    final_results = await current_results()
    yield _format_update({"type": "done", "results": final_results})


async def _rerank_yandex_search_stream(query: str, region: str) -> AsyncIterator[str]:
    async for line in _yandex_search_stream(query, region, rerank=True):
        yield line


@app.get("/yandex_search")
async def yandex_search(
    query: str = Query(..., min_length=1),
    region: str = Query("санкт-петербург", min_length=1),
):
    return StreamingResponse(
        _rerank_yandex_search_stream(query, region),
        media_type=NDJSON_MEDIA_TYPE,
        headers=STREAM_HEADERS,
    )


@app.get("/yandex_search_extended")
async def yandex_search_extended(
    query: str = Query(..., min_length=1),
    region: str = Query("санкт-петербург", min_length=1),
):
    return StreamingResponse(
        _yandex_extended_search_stream(query, region),
        media_type=NDJSON_MEDIA_TYPE,
        headers=STREAM_HEADERS,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        # host="0.0.0.0",
        host="127.0.0.1",
        port=9005,
        reload=False,
        root_path=API_PREFIX,
    )
