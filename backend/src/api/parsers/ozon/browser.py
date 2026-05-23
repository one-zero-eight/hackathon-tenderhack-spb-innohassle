from __future__ import annotations

import logging
from pathlib import Path

from selenium_driverless import webdriver
from selenium_driverless.webdriver import Chrome

from src.api.parsers.chrome_fast import apply_fast_chrome_args
from src.api.parsers.ozon.proxy import apply_proxy
from src.api.parsers.ozon.session import prime_session_with_cookies, warmup_ozon_session
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
    apply_fast_chrome_args(options)
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
    cookies_path = Path(cookies_file) if cookies_file else None
    nav_retries = page_load_retries if slow_mode else min(page_load_retries, 2)

    driver = webdriver.Chrome(options=options)
    await driver.start_session()

    logger.info(
        "Chrome + selenium-driverless (headless=%s, proxy=%s, cookies=%s)",
        headless,
        via_proxy,
        bool(cookies_path),
    )

    if cookies_path and cookies_path.exists():
        await prime_session_with_cookies(
            driver,
            cookies_path,
            via_proxy=via_proxy,
            page_load_timeout=page_load_timeout,
            slow=slow_mode,
        )
    else:
        await warmup_ozon_session(
            driver,
            slow=slow_mode,
            headless=headless,
            via_proxy=via_proxy,
            page_load_timeout=page_load_timeout,
            element_wait_timeout=element_wait_timeout,
            page_load_retries=nav_retries,
        )

    return driver, user_agent, via_proxy
