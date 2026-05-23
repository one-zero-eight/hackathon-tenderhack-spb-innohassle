from __future__ import annotations

import logging
import shutil
from pathlib import Path

from selenium_driverless import webdriver
from selenium_driverless.webdriver import Chrome

from src.api.parsers.ozon.user_agent import pick_user_agent
from src.config import wildberries_settings

logger = logging.getLogger(__name__)

HEADLESS_WINDOW = (1920, 1080)
CHROME_EXECUTABLE_CANDIDATES = (
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def _resolve_chrome_executable_path() -> str | None:
    configured = wildberries_settings.chrome_executable_path
    if configured and Path(configured).is_file():
        return configured

    for path in CHROME_EXECUTABLE_CANDIDATES:
        if Path(path).is_file():
            return path

    for binary in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(binary)
        if found:
            return found

    return None


def _build_chrome_options(*, headless: bool) -> tuple[webdriver.ChromeOptions, str]:
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=ru-RU")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-popup-blocking")

    user_agent = pick_user_agent()
    options.add_argument(f"--user-agent={user_agent}")
    logger.info("Wildberries User-Agent: %s", user_agent)

    if headless:
        options.headless = True
        width, height = HEADLESS_WINDOW
        options.add_argument(f"--window-size={width},{height}")
    else:
        options.add_argument("--start-maximized")

    chrome_executable_path = _resolve_chrome_executable_path()
    if chrome_executable_path:
        options.binary_location = chrome_executable_path

    return options, user_agent


async def create_driverless_driver(*, headless: bool = True) -> tuple[Chrome, str]:
    options, user_agent = _build_chrome_options(headless=headless)
    driver = webdriver.Chrome(options=options)
    await driver.start_session()
    logger.info("Wildberries Chrome + selenium-driverless (headless=%s)", headless)
    return driver, user_agent
