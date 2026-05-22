"""
Wildberries Price Search Script
Uses Playwright (real Chromium headless) to bypass Qrator PoW challenge.
Intercepts the internal search.wb.ru API call and extracts product data.

Requirements:
    pip install playwright
    PLAYWRIGHT_BROWSERS_PATH=~/.playwright python -m playwright install chromium
"""
import asyncio
import json
import sys
import os
import re

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(os.path.expanduser("~/.playwright")))


async def _search(query: str, limit: int) -> list[dict]:
    from playwright.async_api import async_playwright

    results = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--lang=ru-RU,ru"],
        )
        context = await browser.new_context(
            locale="ru-RU",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        # Capture responses from search.wb.ru
        api_data: list[dict] = []

        async def handle_response(response):
            if "search.wb.ru" in response.url and "resultset=catalog" in response.url:
                try:
                    data = await response.json()
                    api_data.append(data)
                except Exception:
                    pass

        page.on("response", handle_response)

        search_url = (
            f"https://www.wildberries.ru/catalog/0/search.aspx"
            f"?search={query.replace(' ', '+')}"
        )

        try:
            await page.goto(search_url, timeout=30000, wait_until="domcontentloaded")
        except Exception:
            pass

        # Wait for the WB JS challenge to complete and products to load
        await asyncio.sleep(8)

        if api_data:
            products_raw = api_data[0].get("data", {}).get("products", [])
            results = _format_products(products_raw[:limit])

        if not results:
            # Fallback: parse DOM
            html = await page.content()
            results = _parse_from_html(html, limit)

        await browser.close()

    return results


def _format_products(products_raw: list) -> list[dict]:
    results = []
    for p in products_raw:
        pid = p.get("id")
        if not pid:
            continue

        vol = pid // 100000
        part = pid // 1000
        basket_ranges = [
            (143, "01"), (287, "02"), (431, "03"), (719, "04"),
            (1007, "05"), (1061, "06"), (1115, "07"), (1169, "08"),
            (1313, "09"), (1601, "10"), (1655, "11"), (1919, "12"),
            (2045, "13"), (2189, "14"), (2405, "15"), (2621, "16"),
            (2837, "17"),
        ]
        basket = "18"
        for max_vol, num in basket_ranges:
            if vol <= max_vol:
                basket = num
                break

        sizes = p.get("sizes", [])
        if sizes and sizes[0].get("price"):
            sale_price = sizes[0]["price"].get("total", 0) / 100
            orig_price = sizes[0]["price"].get("basic", 0) / 100
        else:
            sale_price = p.get("salePriceU", 0) / 100
            orig_price = p.get("priceU", 0) / 100

        results.append({
            "name": p.get("name", "N/A"),
            "brand": p.get("brand", "N/A"),
            "sale_price": sale_price,
            "original_price": orig_price,
            "rating": p.get("reviewRating", 0),
            "feedbacks": p.get("feedbacks", 0),
            "url": f"https://www.wildberries.ru/catalog/{pid}/detail.aspx",
            "image_url": (
                f"https://basket-{basket}.wbbasket.ru/"
                f"vol{vol}/part{part}/{pid}/images/c516x688/1.webp"
            ),
            "source": "Wildberries",
        })
    return results


def _parse_from_html(html: str, limit: int) -> list[dict]:
    results = []
    match = re.search(r'"products"\s*:\s*(\[.*?\])\s*[,}]', html, re.DOTALL)
    if match:
        try:
            products_raw = json.loads(match.group(1))
            return _format_products(products_raw[:limit])
        except json.JSONDecodeError:
            pass
    return results


def search_wildberries(query: str, limit: int = 5) -> list[dict]:
    return asyncio.run(_search(query, limit))


def main():
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "iPhone 15"
    print(f"🔍 Searching Wildberries for: '{query}'\n")

    try:
        results = search_wildberries(query)

        if not results:
            print("❌ No products found.")
            return

        print(f"✅ Found {len(results)} products:\n")
        for i, p in enumerate(results, 1):
            print(f"{'─' * 60}")
            print(f"  #{i}: {p['brand']} — {p['name']}")
            if p['original_price'] > p['sale_price']:
                print(f"  💰 Price: {p['sale_price']:,.0f} ₽  (was {p['original_price']:,.0f} ₽)")
            else:
                print(f"  💰 Price: {p['sale_price']:,.0f} ₽")
            print(f"  ⭐ {p['rating']} ({p['feedbacks']} отзывов)")
            print(f"  🔗 {p['url']}")
            print(f"  🖼️  {p['image_url']}")
        print(f"\n{'─' * 60}")
        print(f"\n📋 Raw JSON (first result):")
        print(json.dumps(results[0], ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
