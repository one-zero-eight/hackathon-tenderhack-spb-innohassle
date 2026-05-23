"""
Yandex Market Price Search Script
Uses httpx to fetch search page and parse embedded JSON-LD data.
"""
import html as html_lib
import json
import logging
import re
from urllib.parse import urljoin

import httpx

from src.api.parsers.geocoder import resolve_ym_region
from src.api.parsers.ozon.user_agent import pick_user_agent
from src.config import api_settings, yandex_market_settings

logger = logging.getLogger(__name__)

YANDEX_HOME_URL = "https://market.yandex.ru/"
YANDEX_SEARCH_URL = "https://market.yandex.ru/search"
YANDEX_PAGE_SIZE = 8
MAX_YANDEX_PAGES = 20


class YandexMarketAccessError(RuntimeError):
    """Captcha, redirect loop, or anti-bot page from Yandex Market."""


def _build_headers(*, referer: str | None = None) -> dict[str, str]:
    return {
        "User-Agent": pick_user_agent(),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin" if referer else "none",
        "Sec-Fetch-User": "?1",
        "Referer": referer or YANDEX_HOME_URL,
    }


def _is_captcha_response(response: httpx.Response) -> bool:
    url = str(response.url).lower()
    if "showcaptcha" in url or "/captcha" in url:
        return True
    for hop in response.history:
        location = (hop.headers.get("location") or "").lower()
        if "showcaptcha" in location or "/captcha" in location:
            return True
    snippet = (response.text or "")[:8000].lower()
    return any(
        marker in snippet
        for marker in (
            "smartcaptcha",
            "yandex captcha",
            "подтвердите, что запросы",
            "я не робот",
        )
    )


def _ensure_ok_response(response: httpx.Response, *, context: str) -> None:
    if _is_captcha_response(response):
        raise YandexMarketAccessError(
            f"Yandex Market captcha during {context} "
            f"(url={response.url}). Set proxy in yandex_market_settings (RU IP recommended).",
        )
    if response.has_redirect_location:
        location = response.headers.get("location", "")
        raise YandexMarketAccessError(
            f"Yandex Market redirect during {context}: "
            f"{response.status_code} -> {location}",
        )
    if response.status_code >= 400:
        response.raise_for_status()


def _build_client() -> httpx.AsyncClient:
    proxy = yandex_market_settings.resolve_proxy()
    timeout = float(yandex_market_settings.timeout)
    headers = _build_headers()
    kwargs: dict[str, object] = {
        "timeout": timeout,
        "headers": headers,
        "follow_redirects": True,
    }
    if proxy:
        kwargs["proxy"] = proxy
        logger.info("Yandex Market httpx client uses proxy")
    else:
        logger.warning(
            "Yandex Market httpx client without proxy — captcha likely on datacenter IPs",
        )
    return httpx.AsyncClient(**kwargs)  # type: ignore[arg-type]


async def _warmup_client(client: httpx.AsyncClient) -> None:
    response = await client.get(
        YANDEX_HOME_URL,
        headers=_build_headers(),
        follow_redirects=True,
    )
    _ensure_ok_response(response, context="warmup")


async def parse_yandex_market_products(
    query: str,
    limit: int = 5,
    skip: int = 0,
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
    lr = resolve_ym_region(location, api_settings.nominatim_url)
    target_count = skip + limit
    max_pages = min(
        MAX_YANDEX_PAGES,
        max(1, (target_count + YANDEX_PAGE_SIZE - 1) // YANDEX_PAGE_SIZE + 2),
    )
    results: list[dict] = []
    seen_products: set[str] = set()

    logger.info(
        "Yandex Market parse start: query=%r limit=%d skip=%d lr=%d location=%r",
        query,
        limit,
        skip,
        lr,
        location,
    )

    try:
        async with _build_client() as client:
            if yandex_market_settings.warmup:
                await _warmup_client(client)

            for page in range(1, max_pages + 1):
                params: dict[str, object] = {"text": query, "lr": lr}
                if page > 1:
                    params["page"] = page

                response = await client.get(
                    YANDEX_SEARCH_URL,
                    params=params,
                    headers=_build_headers(referer=YANDEX_HOME_URL),
                    follow_redirects=True,
                )
                _ensure_ok_response(response, context=f"search page {page}")

                page_results = _parse_yandex_market_html(response.text, target_count, skip=0)
                if not page_results:
                    logger.info(
                        "Yandex Market: page %d returned no products, stopping",
                        page,
                    )
                    break

                previous_count = len(results)
                for product in page_results:
                    product_key = (
                        product.get("url")
                        or f"{product.get('name')}:{product.get('sale_price')}"
                    )
                    if product_key in seen_products:
                        continue
                    seen_products.add(product_key)
                    results.append(product)
                    if len(results) >= target_count:
                        return results[skip:target_count]

                if len(results) == previous_count:
                    logger.info(
                        "Yandex Market: page %d had no new products, stopping",
                        page,
                    )
                    break

        return results[skip:target_count]
    except YandexMarketAccessError:
        raise
    except Exception as exc:
        logger.exception("Yandex Market parse failed for %r", query)
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
                        "image_url": offer.get("image", ""),
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
                                        "image_url": item.get("image", ""),
                                        "source": "Yandex Market",
                                    })
                                if len(results) >= limit:
                                    return results
            except (json.JSONDecodeError, ValueError):
                pass

    return results[:limit]


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
    pictures = entities.get("avatars_picture", {})

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
        results.append({
            "name": _extract_title(offer) or _extract_title(product) or "N/A",
            "brand": vendor.get("name", "N/A"),
            "sale_price": price,
            "original_price": _extract_original_price(offer) or price,
            "url": url,
            "image_url": _extract_image_url(offer, pictures) or _extract_image_url(product, pictures),
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
    value = (
        ((offer.get("discount") or {}).get("currentPrice") or {}).get("value")
        or (offer.get("price") or {}).get("value")
        or (offer.get("prices") or {}).get("value")
        or (offer.get("prices") or {}).get("rawValue")
    )
    return float(value) if value is not None else None


def _extract_original_price(offer: dict) -> float | None:
    value = ((offer.get("discount") or {}).get("oldPrice") or {}).get("value")
    return float(value) if value is not None else None


def _extract_title(item: dict) -> str | None:
    title = item.get("titles") or item.get("metaTitle", {}).get("title")
    if isinstance(title, dict):
        return title.get("raw")
    return None


def _extract_image_url(item: dict, pictures: dict[str, dict]) -> str | None:
    picture_ids = item.get("skuAwarePictures") or item.get("pictures") or []
    if not isinstance(picture_ids, list):
        return None
    for picture_id in picture_ids:
        if isinstance(picture_id, str) and picture_id.startswith(("http://", "https://", "//")):
            return _absolute_yandex_url(picture_id)
        picture = pictures.get(str(picture_id))
        if picture and picture.get("origUrl"):
            return _absolute_yandex_url(picture["origUrl"])
    return None


def _absolute_yandex_url(url: str) -> str:
    return urljoin("https://market.yandex.ru", url)


def _is_generic_yandex_page_result(offer: dict) -> bool:
    name = str(offer.get("name", "")).lower()
    return "купить по низкой цене на яндекс маркете" in name
