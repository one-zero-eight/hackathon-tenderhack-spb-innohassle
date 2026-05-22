"""
Yandex Market Price Search Script
Uses requests to fetch search page and parse embedded JSON-LD data.
"""
import asyncio
import html as html_lib
import json
import re
from urllib.parse import urljoin

import requests


async def parse_yandex_market_products(query: str, limit: int = 5) -> list[dict]:
    """Parse Yandex Market search results asynchronously."""
    return await asyncio.to_thread(_parse_yandex_market_products_sync, query, limit)


def _parse_yandex_market_products_sync(query: str, limit: int = 5) -> list[dict]:
    """Parse Yandex Market search results via HTML + JSON-LD."""
    url = "https://market.yandex.ru/search"
    params = {"text": query}
    
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
    }
    
    response = requests.get(url, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    html = response.text
    apiary_results = _parse_apiary_results(html, limit)
    if apiary_results:
        return apiary_results

    results = []
    seen_urls = set()
    
    # Strategy 1: JSON-LD
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
    
    # Strategy 2: Regex fallback for price/title in page data
    if not results:
        # YM sometimes embeds initial state in script tags
        state_match = re.search(
            r'<script[^>]*>\s*window\.__INIT_STATE__\s*=\s*(\{.+?\});\s*</script>',
            html, re.DOTALL
        )
        if state_match:
            try:
                state = json.loads(state_match.group(1))
                # Navigate the state tree to find search results
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


def _parse_apiary_results(html: str, limit: int) -> list[dict]:
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
