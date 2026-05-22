import asyncio
import os
import time
from urllib.parse import quote_plus

import undetected_chromedriver as uc
from pyvirtualdisplay import Display
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


async def parse_wildberries_price(keyword: str) -> dict:
    """Parse the first Wildberries product price asynchronously."""
    return await asyncio.to_thread(_parse_wildberries_price_sync, keyword)


def _parse_wildberries_price_sync(keyword: str) -> dict:
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

        print("Launching stealth browser inside virtual display...")
        driver = uc.Chrome(options=options, browser_executable_path="/usr/bin/google-chrome", version_main=148)

        try:
            print(f"Navigating to Wildberries search for: '{keyword}'")
            driver.get(f"https://www.wildberries.ru/catalog/0/search.aspx?search={quote_plus(keyword)}")

            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "article, .product-card")))
            time.sleep(2)

            first_product = driver.find_element(By.CSS_SELECTOR, "article, .product-card")
            price_element = first_product.find_element(By.XPATH, './/*[contains(text(), "₽")]')
            clean_price = "".join(filter(str.isdigit, price_element.text))

            return {"marketplace": "Wildberries", "price": int(clean_price)}

        except Exception as e:
            driver.save_screenshot("server_error_debug.png")
            return {"marketplace": "Wildberries", "error": "Failed to scrape", "details": str(e)}
        finally:
            driver.quit()

    finally:
        display.stop()
