import asyncio
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

CHROME_EXECUTABLE_PATH = "/usr/bin/google-chrome"


async def parse_wildberries_products(keyword: str, limit: int = 5, skip: int = 0) -> list[dict]:
    """Parse Wildberries search results asynchronously."""
    return await asyncio.to_thread(_parse_wildberries_products_sync, keyword, limit, skip)


def _parse_wildberries_products_sync(keyword: str, limit: int = 5, skip: int = 0) -> list[dict]:
    # Hide the real desktop
    leaky_vars = ["WAYLAND_DISPLAY", "XDG_SESSION_TYPE", "DBUS_SESSION_BUS_ADDRESS"]
    for var in leaky_vars:
        if var in os.environ:
            del os.environ[var]

    # Start the invisible monitor
    display = Display(visible=0, size=(1920, 1080))
    display.start()

    try:
        options = uc.ChromeOptions()
        options.headless = False

        # Force Chrome to use the X11 virtual display, not Wayland
        options.add_argument("--ozone-platform=x11")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        print("Launching stealth browser inside virtual display...")
        driver = uc.Chrome(
            options=options,
            browser_executable_path=CHROME_EXECUTABLE_PATH,
            version_main=_get_chrome_major_version(),
        )

        try:
            print(f"Navigating to Wildberries search for: '{keyword}'")
            driver.get(f"https://www.wildberries.ru/catalog/0/search.aspx?search={quote_plus(keyword)}")

            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "article, .product-card")))
            time.sleep(2)

            product_cards = driver.find_elements(By.CSS_SELECTOR, "article, .product-card")
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
