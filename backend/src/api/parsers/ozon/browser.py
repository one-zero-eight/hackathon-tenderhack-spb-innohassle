from __future__ import annotations

import logging
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium_stealth import stealth
from webdriver_manager.chrome import ChromeDriverManager

from src.api.parsers.ozon.navigation import configure_timeouts
from src.api.parsers.ozon.proxy import apply_proxy
from src.api.parsers.ozon.session import merge_cookies_from_file, warmup_ozon_session
from src.api.parsers.ozon.user_agent import pick_user_agent

logger = logging.getLogger(__name__)

HEADLESS_WINDOW = (1920, 1080)


def _apply_headless_options(options: Options) -> None:
    """Chrome headless=new — без GUI, с фиксированным viewport."""
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--hide-scrollbars")


def _apply_user_agent(driver: webdriver.Chrome, user_agent: str) -> None:
    driver.execute_cdp_cmd(
        "Network.setUserAgentOverride",
        {
            "userAgent": user_agent,
            "platform": "MacIntel",
            "acceptLanguage": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )


def create_stealth_driver(
    *,
    headless: bool = False,
    user_data_dir: str | Path | None = None,
    cookies_file: str | Path | None = None,
    slow_mode: bool = False,
    proxy: str | None = None,
    page_load_timeout: int | None = None,
    element_wait_timeout: int = 45,
    page_load_retries: int = 4,
) -> tuple[webdriver.Chrome, str, bool]:
    user_agent = pick_user_agent()
    logger.info("User-Agent: %s", user_agent)

    options = Options()
    options.page_load_strategy = "eager"
    if headless:
        _apply_headless_options(options)
    else:
        options.add_argument("--start-maximized")
    options.add_argument(f"--user-agent={user_agent}")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--lang=ru-RU")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    if user_data_dir:
        options.add_argument(f"--user-data-dir={Path(user_data_dir).resolve()}")

    proxy_settings = apply_proxy(options, proxy)
    via_proxy = proxy_settings is not None

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    if headless:
        w, h = HEADLESS_WINDOW
        driver.set_window_size(w, h)
    _apply_user_agent(driver, user_agent)

    stealth(
        driver,
        languages=["ru-RU", "ru", "en-US", "en"],
        vendor="Google Inc.",
        platform="MacIntel",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    configure_timeouts(driver, via_proxy=via_proxy, page_load_timeout=page_load_timeout)
    driver.implicitly_wait(5)
    logger.info(
        "Chrome + selenium-stealth (headless=%s, proxy=%s)",
        headless,
        via_proxy,
    )

    if via_proxy:
        time.sleep(5)

    warmup_ozon_session(
        driver,
        slow=slow_mode,
        headless=headless,
        via_proxy=via_proxy,
        page_load_timeout=page_load_timeout,
        element_wait_timeout=element_wait_timeout,
        page_load_retries=page_load_retries,
    )

    if cookies_file:
        merge_cookies_from_file(
            driver,
            Path(cookies_file),
            via_proxy=via_proxy,
            page_load_timeout=page_load_timeout,
            page_load_retries=page_load_retries,
        )

    return driver, user_agent, via_proxy
