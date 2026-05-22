"""
Yandex Market Price Search Script
Uses requests to fetch search page and parse embedded JSON-LD data.
"""
import asyncio
import json
import re

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
    results = []
    
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
            
            for item in items[:limit]:
                offer = item.get("item", item)
                offers = offer.get("offers", {})
                price = float(offers.get("lowPrice", offers.get("price", 0)))
                if price > 0:
                    results.append({
                        "name": offer.get("name", "N/A"),
                        "brand": (offer.get("brand", {}).get("name", "N/A")
                                  if isinstance(offer.get("brand"), dict)
                                  else offer.get("brand", "N/A")),
                        "sale_price": price,
                        "original_price": float(
                            offers.get("highPrice", offers.get("price", price))
                        ),
                        "url": offer.get("url", ""),
                        "image_url": offer.get("image", ""),
                        "source": "Yandex Market",
                    })
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
                            for item in val["items"][:limit]:
                                price = item.get("price", {}).get("value", 0)
                                if price:
                                    results.append({
                                        "name": item.get("title", "N/A"),
                                        "brand": item.get("brand", "N/A"),
                                        "sale_price": float(price),
                                        "original_price": float(price),
                                        "url": item.get("url", ""),
                                        "image_url": item.get("image", ""),
                                        "source": "Yandex Market",
                                    })
            except (json.JSONDecodeError, ValueError):
                pass
    
    return results[:limit]
