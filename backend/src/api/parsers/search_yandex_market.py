"""
Yandex Market Price Search Script
Uses httpx to fetch search page and parse embedded JSON-LD data.
"""
import asyncio
import contextlib
import html as html_lib
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from urllib.parse import urljoin

import httpx

from src.api.parsers.geocoder import resolve_ym_region
from src.api.parsers.ozon.user_agent import pick_user_agent
from src.config import yandex_market_settings

logger = logging.getLogger(__name__)

YANDEX_SEARCH_URL = "https://market.yandex.ru/search"
# Apiary SERP usually has ~12–16 offers per page; old value (8) over-estimated page count.
YANDEX_PAGE_SIZE = 16
MAX_YANDEX_PAGES = 20
YM_FETCH_CONCURRENCY = 4
# Moscow region (market.yandex.ru ``lr`` parameter).
YM_MOSCOW_LR = 213


def _build_headers() -> dict[str, str]:
    return {
        "User-Agent": pick_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
    }


def _build_client() -> httpx.AsyncClient:
    proxy = yandex_market_settings.resolve_proxy()
    timeout = httpx.Timeout(
        float(yandex_market_settings.timeout),
        connect=float(yandex_market_settings.connect_timeout),
    )
    kwargs: dict[str, object] = {
        "timeout": timeout,
        "headers": _build_headers(),
        "follow_redirects": True,
        "http2": False,
    }
    if proxy:
        kwargs["proxy"] = proxy
        logger.info("Yandex Market httpx proxy enabled")
    return httpx.AsyncClient(**kwargs)  # type: ignore[arg-type]


def _pages_needed(target_count: int) -> int:
    """How many SERP pages to request over HTTP."""
    return min(
        MAX_YANDEX_PAGES,
        max(1, (target_count + YANDEX_PAGE_SIZE - 1) // YANDEX_PAGE_SIZE),
    )


async def _fetch_search_page(
    client: httpx.AsyncClient,
    *,
    query: str,
    lr: int,
    page: int,
) -> str:
    params: dict[str, object] = {"text": query, "lr": lr}
    if page > 1:
        params["page"] = page

    retries = yandex_market_settings.request_retries
    last_exc: BaseException | None = None
    for attempt in range(1, retries + 1):
        started = time.perf_counter()
        try:
            response = await client.get(YANDEX_SEARCH_URL, params=params)
            response.raise_for_status()
            logger.info(
                "Yandex Market page %d: HTTP %d in %.2fs (%d KB)",
                page,
                response.status_code,
                time.perf_counter() - started,
                len(response.content) // 1024,
            )
            return response.text
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500:
                raise
            logger.warning(
                "Yandex Market page %d attempt %d/%d failed: %s",
                page,
                attempt,
                retries,
                exc,
            )
            if attempt < retries:
                await asyncio.sleep(0.25 * attempt)
    msg = f"Yandex Market page {page} failed after {retries} attempts"
    raise RuntimeError(msg) from last_exc


async def _fetch_search_pages_parallel(
    client: httpx.AsyncClient,
    *,
    query: str,
    lr: int,
    page_numbers: list[int],
) -> dict[int, str]:
    if not page_numbers:
        return {}

    sem = asyncio.Semaphore(YM_FETCH_CONCURRENCY)

    async def fetch_one(page: int) -> tuple[int, str | None]:
        async with sem:
            try:
                html = await _fetch_search_page(client, query=query, lr=lr, page=page)
                return page, html
            except Exception as exc:
                logger.warning("Yandex Market page %d fetch failed: %s", page, exc)
                return page, None

    started = time.perf_counter()
    pairs = await asyncio.gather(*(fetch_one(page) for page in page_numbers))
    pages = {page: html for page, html in pairs if html}
    logger.info(
        "Yandex Market parallel fetch: %d/%d pages in %.2fs (concurrency=%d)",
        len(pages),
        len(page_numbers),
        time.perf_counter() - started,
        YM_FETCH_CONCURRENCY,
    )
    return pages


async def _load_serp_pages(
    client: httpx.AsyncClient,
    *,
    query: str,
    lr: int,
    max_pages: int,
) -> dict[int, str]:
    """Load all SERP pages in parallel (bounded concurrency)."""
    if max_pages <= 0:
        return {}
    if max_pages == 1:
        return {1: await _fetch_search_page(client, query=query, lr=lr, page=1)}

    return await _fetch_search_pages_parallel(
        client,
        query=query,
        lr=lr,
        page_numbers=list(range(1, max_pages + 1)),
    )


def _product_key(product: dict) -> str:
    return product.get("url") or f"{product.get('name')}:{product.get('sale_price')}"


async def parse_yandex_market_products(
    query: str,
    limit: int = 5,
    skip: int = 0,
    *,
    lr: int = YM_MOSCOW_LR,
    location: str | None = None,
) -> list[dict]:
    """Parse Yandex Market search results asynchronously.

    Args:
        query: Search query.
        limit: Maximum number of results.
        skip: Number of results to skip.
        location: City/region for regional pricing (e.g. 'Санкт-Петербург').
                  Defaults to Moscow when omitted.
    """
    lr = resolve_ym_region(location)
    target_count = skip + limit
    max_pages = _pages_needed(target_count)
    results: list[dict] = []
    seen_products: set[str] = set()
    fetch_started = time.perf_counter()

    logger.info(
        "Yandex Market parse start: query=%r limit=%d skip=%d lr=%d "
        "(up to %d HTTP pages, parallel concurrency=%d)",
        query,
        limit,
        skip,
        lr,
        max_pages,
        YM_FETCH_CONCURRENCY,
    )

    try:
        async with _build_client() as client:
            pages_html = await _load_serp_pages(
                client,
                query=query,
                lr=lr,
                max_pages=max_pages,
            )
            pages_fetched = 0
            for page in range(1, max_pages + 1):
                html = pages_html.get(page)
                if not html:
                    continue
                pages_fetched += 1
                page_results = _parse_yandex_market_html(html, target_count, skip=0)
                if not page_results:
                    logger.info(
                        "Yandex Market: page %d returned no products, stopping",
                        page,
                    )
                    break

                previous_count = len(results)
                for product in page_results:
                    key = _product_key(product)
                    if key in seen_products:
                        continue
                    seen_products.add(key)
                    results.append(product)
                    if len(results) >= target_count:
                        logger.info(
                            "Yandex Market parse done: %d items in %.2fs "
                            "(%d pages fetched, parallel)",
                            len(results[skip:target_count]),
                            time.perf_counter() - fetch_started,
                            pages_fetched,
                        )
                        return results[skip:target_count]

                if len(results) == previous_count:
                    logger.info(
                        "Yandex Market: page %d had no new products, stopping",
                        page,
                    )
                    break

        logger.info(
            "Yandex Market parse done: %d items in %.2fs (%d pages fetched, parallel)",
            len(results[skip:target_count]),
            time.perf_counter() - fetch_started,
            pages_fetched,
        )
        return results[skip:target_count]
    except Exception as exc:
        logger.exception("Yandex Market parse failed for %r", query)
        raise RuntimeError(f"Failed to scrape Yandex Market: {exc}") from exc


async def iter_yandex_market_products(
    query: str,
    limit: int = 5,
    skip: int = 0,
    *,
    lr: int = YM_MOSCOW_LR,
    location: str | None = None,
) -> AsyncIterator[list[dict]]:
    """Yield Yandex Market products page-by-page as they are parsed."""
    lr = resolve_ym_region(location)
    target_count = skip + limit
    max_pages = _pages_needed(target_count)
    seen_products: set[str] = set()
    skipped_count = 0
    emitted = 0
    new_on_page = 0
    stream_started = time.perf_counter()

    logger.info(
        "Yandex Market stream start: query=%r limit=%d skip=%d lr=%d "
        "(up to %d HTTP pages, parallel concurrency=%d)",
        query,
        limit,
        skip,
        lr,
        max_pages,
        YM_FETCH_CONCURRENCY,
    )

    try:
        async with _build_client() as client:
            rest_task: asyncio.Task[dict[int, str]] | None = None
            if max_pages > 1:
                rest_task = asyncio.create_task(
                    _fetch_search_pages_parallel(
                        client,
                        query=query,
                        lr=lr,
                        page_numbers=list(range(2, max_pages + 1)),
                    )
                )

            pages_processed = 0
            page_html_items: list[tuple[int, str]] = [
                (1, await _fetch_search_page(client, query=query, lr=lr, page=1)),
            ]

            async def _cancel_rest_task() -> None:
                if rest_task is None:
                    return
                rest_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await rest_task

            for page, html in page_html_items:
                pages_processed += 1
                page_results = _parse_yandex_market_html(html, target_count, skip=0)
                if not page_results:
                    logger.info(
                        "Yandex Market: page %d returned no products, stopping",
                        page,
                    )
                    await _cancel_rest_task()
                    break

                new_on_page = 0
                page_batch: list[dict] = []
                for product in page_results:
                    key = _product_key(product)
                    if key in seen_products:
                        continue
                    seen_products.add(key)

                    if skipped_count < skip:
                        skipped_count += 1
                        continue
                    if emitted >= limit:
                        if page_batch:
                            yield page_batch
                        await _cancel_rest_task()
                        return

                    page_batch.append(product)
                    emitted += 1
                    new_on_page += 1

                if page_batch:
                    yield page_batch

                if emitted >= limit:
                    await _cancel_rest_task()
                    return

                if new_on_page == 0:
                    logger.info(
                        "Yandex Market: page %d had no new products, stopping",
                        page,
                    )
                    await _cancel_rest_task()
                    break

                if page == 1 and rest_task is not None:
                    try:
                        rest_pages = await rest_task
                    except Exception:
                        await _cancel_rest_task()
                        raise
                    page_html_items.extend(
                        (p, rest_pages[p])
                        for p in range(2, max_pages + 1)
                        if p in rest_pages
                    )

        logger.info(
            "Yandex Market stream done: emitted=%d limit=%d in %.2fs "
            "(%d pages processed, parallel)",
            emitted,
            limit,
            time.perf_counter() - stream_started,
            pages_processed,
        )
    except Exception as exc:
        logger.exception("Yandex Market stream failed for %r", query)
        raise RuntimeError(f"Failed to scrape Yandex Market: {exc}") from exc


def _parse_yandex_market_html(html: str, limit: int = 5, skip: int = 0) -> list[dict]:
    """Parse Yandex Market search results from HTML."""
    apiary_results = _parse_apiary_results(html, limit, skip)
    if apiary_results:
        return apiary_results

    results = []
    seen_urls = set()
    jsonld_matches = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
    )
    for jsonld_str in jsonld_matches:
        try:
            jsonld = json.loads(jsonld_str)
            items = []
            if isinstance(jsonld, dict):
                if jsonld.get("@type") == "ItemList":
                    items = jsonld.get("itemListElement", [])
                elif jsonld.get("@type") == "Product":
                    items = [{"item": jsonld}]
            elif isinstance(jsonld, list):
                items = [{"item": j} for j in jsonld if j.get("@type") == "Product"]

            for item in items:
                offer = item.get("item", item)
                if _is_generic_yandex_page_result(offer):
                    continue
                offers = offer.get("offers", {})
                price = float(offers.get("lowPrice", offers.get("price", 0)))
                url = offer.get("url", "")
                if price > 0 and url not in seen_urls:
                    seen_urls.add(url)
                    results.append({
                        "name": offer.get("name", "N/A"),
                        "brand": (offer.get("brand", {}).get("name", "N/A")
                                  if isinstance(offer.get("brand"), dict)
                                  else offer.get("brand", "N/A")),
                        "sale_price": price,
                        "original_price": float(
                            offers.get("highPrice", offers.get("price", price))
                        ),
                        "url": url,
                        "image_url": _jsonld_image_url(offer),
                        "source": "Yandex Market",
                    })
                if len(results) >= limit:
                    return results
        except (json.JSONDecodeError, ValueError):
            continue

    if not results:
        state_match = re.search(
            r'<script[^>]*>\s*window\.__INIT_STATE__\s*=\s*(\{.+?\});\s*</script>',
            html, re.DOTALL
        )
        if state_match:
            try:
                state = json.loads(state_match.group(1))
                search_data = state.get("searchPage", state)
                if isinstance(search_data, dict):
                    for key, val in search_data.items():
                        if isinstance(val, dict) and "items" in val:
                            for item in val["items"]:
                                price = item.get("price", {}).get("value", 0)
                                url = item.get("url", "")
                                if price and url not in seen_urls:
                                    seen_urls.add(url)
                                    results.append({
                                        "name": item.get("title", "N/A"),
                                        "brand": item.get("brand", "N/A"),
                                        "sale_price": float(price),
                                        "original_price": float(price),
                                        "url": url,
                                        "image_url": _jsonld_image_url(item),
                                        "source": "Yandex Market",
                                    })
                                if len(results) >= limit:
                                    return results
            except (json.JSONDecodeError, ValueError):
                pass

    return results[:limit]


def _merge_picture_entities(entities: dict[str, dict[str, dict]]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for entity_name in (
        "avatars_picture",
        "picture",
        "mediaItem",
        "photo",
        "thumbnail",
    ):
        merged.update(entities.get(entity_name, {}))
    return merged


def _parse_apiary_results(html: str, limit: int, skip: int = 0) -> list[dict]:
    entities = _extract_apiary_entities(html)
    if not entities:
        return []

    visible_entities = entities.get("visibleEntity", {})
    product_show_places = entities.get("productShowPlace", {})
    offer_show_places = entities.get("offerShowPlace", {})
    offers = entities.get("offer", {})
    products = entities.get("product", {})
    vendors = entities.get("vendor", {})
    pictures = _merge_picture_entities(entities)

    visible_ids = _get_visible_entity_ids(entities)
    results = []
    seen_urls = set()
    skipped = 0

    for visible_id in visible_ids:
        visible_entity = visible_entities.get(str(visible_id))
        if not visible_entity:
            continue

        product_show_place = product_show_places.get(str(visible_entity.get("productShowPlaceId")))
        if not product_show_place:
            continue

        offer_show_place_id = product_show_place.get("defaultOfferShowPlaceId")
        if not offer_show_place_id:
            offer_show_place_ids = product_show_place.get("offerShowPlaceIds") or []
            offer_show_place_id = offer_show_place_ids[0] if offer_show_place_ids else None
        if not offer_show_place_id:
            continue

        offer_show_place = offer_show_places.get(str(offer_show_place_id))
        if not offer_show_place:
            continue

        offer = offers.get(str(offer_show_place.get("offerId")))
        if not offer:
            continue

        price = _extract_offer_price(offer)
        if price is None:
            continue

        product = products.get(str(product_show_place.get("productId")), {})
        url = _absolute_yandex_url(
            (offer_show_place.get("urls") or {}).get("direct")
            or (product_show_place.get("urls") or {}).get("direct")
            or ""
        )
        if url in seen_urls:
            continue
        seen_urls.add(url)
        if skipped < skip:
            skipped += 1
            continue

        vendor_id = offer.get("vendorId") or product.get("vendorId")
        vendor = vendors.get(str(vendor_id), {})
        brand = vendor.get("name") or vendor.get("slug")
        image_url = (
            _extract_image_url(offer, pictures)
            or _extract_image_url(product, pictures)
            or _extract_image_url(product_show_place, pictures)
            or _extract_image_url(offer_show_place, pictures)
        )
        results.append({
            "name": _extract_title(offer) or _extract_title(product) or "N/A",
            "brand": brand if brand else None,
            "sale_price": price,
            "original_price": _extract_original_price(offer) or price,
            "url": url,
            "image_url": image_url,
            "source": "Yandex Market",
        })

        if len(results) >= limit:
            break

    return results


def _extract_apiary_entities(html: str) -> dict[str, dict[str, dict]]:
    entities: dict[str, dict[str, dict]] = {}
    patch_matches = re.findall(r'<noframes data-apiary="patch">(.*?)</noframes>', html, re.DOTALL)
    for patch_str in patch_matches:
        try:
            patch = json.loads(html_lib.unescape(patch_str))
        except json.JSONDecodeError:
            continue
        _collect_entities(patch, entities)
    return entities


def _collect_entities(value: object, entities: dict[str, dict[str, dict]]) -> None:
    if isinstance(value, dict):
        entity = value.get("entity")
        entity_id = value.get("id")
        if isinstance(entity, str) and entity_id is not None:
            entities.setdefault(entity, {})[str(entity_id)] = value
        for child in value.values():
            _collect_entities(child, entities)
    elif isinstance(value, list):
        for item in value:
            _collect_entities(item, entities)


def _get_visible_entity_ids(entities: dict[str, dict[str, dict]]) -> list[str]:
    for search_result in entities.get("searchResult", {}).values():
        visible_ids = search_result.get("visibleEntityIds")
        if isinstance(visible_ids, list) and visible_ids:
            return [str(visible_id) for visible_id in visible_ids]
    return list(entities.get("visibleEntity", {}).keys())


def _extract_offer_price(offer: dict) -> float | None:
    candidates = [
        ((offer.get("discount") or {}).get("currentPrice") or {}).get("value"),
        ((offer.get("discount") or {}).get("price") or {}).get("value"),
        (offer.get("price") or {}).get("value"),
        (offer.get("prices") or {}).get("value"),
        (offer.get("prices") or {}).get("rawValue"),
        offer.get("priceValue"),
    ]
    for value in candidates:
        if value is not None:
            try:
                amount = float(value)
            except (TypeError, ValueError):
                continue
            if amount > 0:
                return amount
    return None


def _extract_original_price(offer: dict) -> float | None:
    value = ((offer.get("discount") or {}).get("oldPrice") or {}).get("value")
    return float(value) if value is not None else None


def _extract_title(item: dict) -> str | None:
    title = item.get("titles") or item.get("metaTitle", {}).get("title")
    if isinstance(title, dict):
        return title.get("raw")
    return None


def _jsonld_image_url(item: dict) -> str | None:
    image = item.get("image")
    if isinstance(image, str):
        return _normalize_yandex_image_url(image)
    if isinstance(image, list):
        for entry in image:
            if isinstance(entry, str):
                normalized = _normalize_yandex_image_url(entry)
                if normalized:
                    return normalized
            if isinstance(entry, dict):
                normalized = _picture_url_from_entity(entry)
                if normalized:
                    return normalized
    if isinstance(image, dict):
        return _picture_url_from_entity(image)
    return None


def _extract_image_url(item: dict, pictures: dict[str, dict]) -> str | None:
    refs: list[object] = []
    for key in (
        "skuAwarePictures",
        "pictures",
        "picture",
        "mainPicture",
        "previewPicture",
        "gallery",
        "photos",
        "images",
    ):
        value = item.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            refs.extend(value)
        else:
            refs.append(value)

    for ref in refs:
        if isinstance(ref, str):
            if ref.startswith(("http://", "https://", "//", "/get-")):
                normalized = _normalize_yandex_image_url(ref)
                if normalized:
                    return normalized
            picture = pictures.get(ref)
            if picture:
                normalized = _picture_url_from_entity(picture)
                if normalized:
                    return normalized
            continue
        if isinstance(ref, dict):
            normalized = _picture_url_from_entity(ref)
            if normalized:
                return normalized
            picture_id = ref.get("id")
            if picture_id is not None:
                picture = pictures.get(str(picture_id))
                if picture:
                    normalized = _picture_url_from_entity(picture)
                    if normalized:
                        return normalized
    return None


def _picture_url_from_entity(picture: dict) -> str | None:
    for key in ("origUrl", "url", "src", "original"):
        value = picture.get(key)
        if isinstance(value, str) and value.strip():
            return _normalize_yandex_image_url(value)

    namespace = picture.get("namespace")
    group_id = picture.get("groupId")
    pic_key = picture.get("key")
    if namespace and group_id is not None and pic_key:
        ns = str(namespace)
        if ns == "mpic":
            ns = "get-mpic"
        elif not ns.startswith("get-"):
            ns = f"get-{ns}"
        built = f"https://avatars.mds.yandex.net/{ns}/{group_id}/{pic_key}/orig"
        return _normalize_yandex_image_url(built)
    return None


def _normalize_yandex_image_url(url: str) -> str | None:
    trimmed = url.strip()
    if not trimmed:
        return None
    if trimmed.startswith("//"):
        return f"https:{trimmed}"
    if trimmed.startswith("/get-"):
        return f"https://avatars.mds.yandex.net{trimmed}"
    broken = re.match(r"^https?://market\.yandex\.ru(/get-[^?#]+)", trimmed, re.IGNORECASE)
    if broken:
        return f"https://avatars.mds.yandex.net{broken.group(1)}"
    if trimmed.startswith("http://") or trimmed.startswith("https://"):
        return trimmed
    return _absolute_yandex_url(trimmed)


def _absolute_yandex_url(url: str) -> str:
    return urljoin("https://market.yandex.ru", url)


def _is_generic_yandex_page_result(offer: dict) -> bool:
    name = str(offer.get("name", "")).lower()
    return "купить по низкой цене на яндекс маркете" in name
