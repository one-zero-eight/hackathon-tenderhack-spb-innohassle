import asyncio
import json
import os
import re
import subprocess
import time
from urllib.parse import quote_plus

import undetected_chromedriver as uc
from pyvirtualdisplay import Display
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.api.logging_ import logger
from src.api.parsers.geocoder import resolve_wb_dest
from src.config import api_settings

CHROME_EXECUTABLE_PATH = "/usr/bin/google-chrome"
MAX_SCROLL_ATTEMPTS = 30
SCROLL_PAUSE_SECONDS = 1


async def parse_wildberries_products(keyword: str, limit: int = 5, skip: int = 0, location: str | None = None) -> list[dict]:
    """Parse Wildberries search results asynchronously.

    Args:
        keyword:  Search query.
        limit:    Maximum number of results.
        skip:     Number of results to skip.
        location: City/region name for localised pricing (e.g. 'Санкт-Петербург').
                  Defaults to Moscow when omitted.
    """
    dest = resolve_wb_dest(location, api_settings.nominatim_url)
    return await asyncio.to_thread(_parse_wildberries_products_sync, keyword, limit, skip, dest)


def _parse_wildberries_products_sync(keyword: str, limit: int = 5, skip: int = 0, dest: int = -1257786) -> list[dict]:
    # Hide the real desktop
    leaky_vars = ["WAYLAND_DISPLAY", "XDG_SESSION_TYPE", "DBUS_SESSION_BUS_ADDRESS"]
    for var in leaky_vars:
        if var in os.environ:
            del os.environ[var]

    # Start the invisible monitor
    display = Display(visible=False, size=(1920, 1080))
    display.start()

    try:
        options = uc.ChromeOptions()
        options.headless = False

        # Force Chrome to use the X11 virtual display, not Wayland
        options.add_argument("--ozone-platform=x11")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        logger.info("Launching stealth browser inside virtual display...")
        driver = uc.Chrome(
            options=options,
            browser_executable_path=CHROME_EXECUTABLE_PATH,
            version_main=_get_chrome_major_version(),
        )

        try:
            logger.info(f"Navigating to Wildberries search for: '{keyword}' (dest={dest})")
            driver.get(f"https://www.wildberries.ru/catalog/0/search.aspx?search={quote_plus(keyword)}&dest={dest}")

            # Inject the geo cookie so subsequent XHR calls from the page also use the correct region
            geo_cookie_value = json.dumps({"id": dest})
            for cookie_name in ("wbx-geo", "GeoIdsJson"):
                driver.add_cookie({
                    "name": cookie_name,
                    "value": geo_cookie_value,
                    "domain": ".wildberries.ru",
                    "path": "/",
                })
            # Reload so WB JS picks up the region cookie
            driver.get(f"https://www.wildberries.ru/catalog/0/search.aspx?search={quote_plus(keyword)}&dest={dest}")

            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "article, .product-card")))
            time.sleep(2)

            product_cards = _load_product_cards(driver, skip + limit)
            products = []
            skipped = 0
            for card in product_cards:
                product = _parse_product_card(card)
                if product.get("sale_price") is None:
                    continue
                if skipped < skip:
                    skipped += 1
                    continue
                products.append(product)
                if len(products) >= limit:
                    break
            return products

        except Exception as e:
            driver.save_screenshot("server_error_debug.png")
            raise RuntimeError(f"Failed to scrape Wildberries: {e}") from e
        finally:
            driver.quit()

    finally:
        display.stop()


def _load_product_cards(driver, target_count: int):
    previous_count = 0
    stable_attempts = 0

    for _ in range(MAX_SCROLL_ATTEMPTS):
        product_cards = driver.find_elements(By.CSS_SELECTOR, "article, .product-card")
        if len(product_cards) >= target_count:
            return product_cards

        if len(product_cards) == previous_count:
            stable_attempts += 1
        else:
            stable_attempts = 0

        if stable_attempts >= 3:
            return product_cards

        previous_count = len(product_cards)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_SECONDS)

    return driver.find_elements(By.CSS_SELECTOR, "article, .product-card")


def _parse_product_card(card) -> dict:
    price_text = _find_text(card, ".price__lower-price, .price__wrap, .product-card__price")
    original_price_text = _find_text(card, "del, .price__wrap del, .product-card__price-old")

    link = _find_attribute(card, "a.product-card__link, a[href*='/catalog/']", "href")
    image_url = _find_attribute(card, "img", "src") or _find_attribute(card, "img", "data-src")

    return {
        "name": _clean_name(_find_text(card, ".product-card__name, .goods-name")),
        "brand": _clean_text(_find_text(card, ".product-card__brand, .brand-name")),
        "sale_price": _parse_price(price_text),
        "original_price": _parse_price(original_price_text),
        "url": link,
        "image_url": image_url,
        "source": "Wildberries",
    }


def _get_chrome_major_version() -> int | None:
    try:
        result = subprocess.run(
            [CHROME_EXECUTABLE_PATH, "--product-version"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    version = result.stdout.strip()
    major_version = version.split(".", maxsplit=1)[0]
    return int(major_version) if major_version.isdigit() else None


def _find_text(card, selector: str) -> str | None:
    try:
        text = card.find_element(By.CSS_SELECTOR, selector).text
    except Exception:
        return None
    return _clean_text(text)


def _find_attribute(card, selector: str, attribute: str) -> str | None:
    try:
        value = card.find_element(By.CSS_SELECTOR, selector).get_attribute(attribute)
    except Exception:
        return None
    return _clean_text(value)


def _parse_price(value: str | None) -> int | None:
    if not value:
        return None
    price_match = re.search(r"(\d[\d\s\u00a0]*)\s*₽", value)
    clean_price = "".join(filter(str.isdigit, price_match.group(1) if price_match else value))
    return int(clean_price) if clean_price else None


def _clean_name(value: str | None) -> str | None:
    if not value:
        return None
    return value.removeprefix("/").strip() or None


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    return " ".join(value.split()) or None
