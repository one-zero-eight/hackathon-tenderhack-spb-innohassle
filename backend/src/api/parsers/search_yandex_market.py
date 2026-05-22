"""
Yandex Market Price Search Script
Uses requests to fetch search page and parse embedded JSON-LD data.
"""
import requests
import sys
import json
import re


def search_yandex_market(query: str, limit: int = 5) -> list[dict]:
    """Search Yandex Market via HTML + JSON-LD parsing."""
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


def main():
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "iPhone 15"
    print(f"🔍 Searching Yandex Market for: '{query}'\n")
    
    try:
        results = search_yandex_market(query)
        
        if not results:
            print("❌ No products found via HTML parsing.")
            print("   Yandex Market has strong anti-bot protection (SmartCaptcha).")
            print("   Consider using Playwright with stealth settings + proxies.")
            return
        
        print(f"✅ Found {len(results)} products:\n")
        for i, p in enumerate(results, 1):
            print(f"{'─' * 60}")
            print(f"  #{i}: {p['name']}")
            if p['brand'] != 'N/A':
                print(f"  🏷️  Brand: {p['brand']}")
            print(f"  💰 Price: {p['sale_price']:,.0f} ₽")
            print(f"  🔗 {p['url']}")
        print(f"\n{'─' * 60}")
        print(f"\n📋 Raw JSON (first result):")
        print(json.dumps(results[0], ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
