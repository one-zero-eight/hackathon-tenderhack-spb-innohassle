from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from selenium_driverless import webdriver
from selenium_driverless.webdriver import Chrome

from src.api.parsers.ozon.proxy import apply_proxy
from src.api.parsers.ozon.session import merge_cookies_from_file, warmup_ozon_session
from src.api.parsers.ozon.user_agent import pick_user_agent

logger = logging.getLogger(__name__)

HEADLESS_WINDOW = (1920, 1080)


def _build_chrome_options(
    *,
    headless: bool,
    user_data_dir: str | Path | None,
    proxy: str | None,
) -> tuple[webdriver.ChromeOptions, str]:
    options = webdriver.ChromeOptions()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=ru-RU")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    user_agent = pick_user_agent()
    options.add_argument(f"--user-agent={user_agent}")
    logger.info("User-Agent: %s", user_agent)

    if headless:
        options.headless = True
        width, height = HEADLESS_WINDOW
        options.add_argument(f"--window-size={width},{height}")
    else:
        options.add_argument("--start-maximized")

    if user_data_dir:
        options.user_data_dir = str(Path(user_data_dir).resolve())

    apply_proxy(options, proxy)
    return options, user_agent


async def create_driverless_driver(
    *,
    headless: bool = False,
    user_data_dir: str | Path | None = None,
    cookies_file: str | Path | None = None,
    slow_mode: bool = False,
    proxy: str | None = None,
    page_load_timeout: int | None = None,
    element_wait_timeout: int = 45,
    page_load_retries: int = 4,
) -> tuple[Chrome, str, bool]:
    options, user_agent = _build_chrome_options(
        headless=headless,
        user_data_dir=user_data_dir,
        proxy=proxy,
    )
    via_proxy = proxy is not None

    driver = webdriver.Chrome(options=options)
    await driver.start_session()

    logger.info(
        "Chrome + selenium-driverless (headless=%s, proxy=%s)",
        headless,
        via_proxy,
    )

    if via_proxy:
        await asyncio.sleep(5)

    await warmup_ozon_session(
        driver,
        slow=slow_mode,
        headless=headless,
        via_proxy=via_proxy,
        page_load_timeout=page_load_timeout,
        element_wait_timeout=element_wait_timeout,
        page_load_retries=page_load_retries,
    )

    if cookies_file:
        await merge_cookies_from_file(
            driver,
            Path(cookies_file),
            via_proxy=via_proxy,
            page_load_timeout=page_load_timeout,
            page_load_retries=page_load_retries,
        )

    return driver, user_agent, via_proxy
