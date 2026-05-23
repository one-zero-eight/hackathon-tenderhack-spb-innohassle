from __future__ import annotations

import asyncio
import logging
import random
from pathlib import Path

from selenium_driverless.types.by import By
from selenium_driverless.types.webelement import NoSuchElementException
from selenium_driverless.webdriver import Chrome

from src.api.parsers.ozon.cookies_loader import apply_cookies, resolve_cookies_path
from src.api.parsers.ozon.exceptions import OzonAccessError
from src.api.parsers.ozon.navigation import DEFAULT_ELEMENT_WAIT, safe_get
from src.api.parsers.wait import wait_for_css

logger = logging.getLogger(__name__)

OZON_HOME = "https://www.ozon.ru/"
BLOCKED_MARKERS = (
    "antibot",
    "captcha",
    "доступ ограничен",
    "доступ запрещен",
    "подтвердите",
    "не робот",
    "похоже, нет соединения",
)
SEARCH_INPUT_CSS = (
    'input[name="text"], '
    'input[placeholder*="Искать"], '
    'input[placeholder*="искать"]'
)


async def _sleep(min_sec: float, max_sec: float | None = None) -> None:
    await asyncio.sleep(random.uniform(min_sec, max_sec or min_sec))


async def _is_blocked(driver: Chrome) -> bool:
    try:
        body = await driver.execute_script(
            "return document.body ? document.body.innerText : ''",
        )
        url = (await driver.current_url).lower()
        blob = f"{url} {(body or '').lower()}"
        return any(m in blob for m in BLOCKED_MARKERS)
    except Exception:
        return False


async def _dismiss_overlays(driver: Chrome) -> None:
    for xpath in (
        "//button[contains(.,'OK')]",
        "//button[contains(.,'Понятно')]",
        "//button[contains(.,'Принять')]",
    ):
        try:
            btn = await driver.find_element(By.XPATH, xpath, timeout=1)
            if await btn.is_visible():
                await btn.click()
                await _sleep(0.2, 0.4)
        except Exception:
            continue


async def _count_ozon_cookies(driver: Chrome) -> int:
    cookies = await driver.get_cookies()
    return sum(1 for cookie in cookies if "ozon" in (cookie.get("domain") or ""))


async def warmup_ozon_session(
    driver: Chrome,
    *,
    slow: bool = False,
    headless: bool = False,
    via_proxy: bool = False,
    page_load_timeout: int | None = None,
    element_wait_timeout: int = DEFAULT_ELEMENT_WAIT,
    page_load_retries: int = 2,
) -> int:
    wait = (4.0, 6.0) if slow else (1.0, 2.0)
    manual_wait = 90 if via_proxy and not headless else (60 if not headless else 45)
    nav_retries = page_load_retries if slow else min(page_load_retries, 2)

    logger.info("Warmup: opening %s", OZON_HOME)
    await safe_get(
        driver,
        OZON_HOME,
        via_proxy=via_proxy,
        page_load_timeout=page_load_timeout,
        retries=nav_retries,
        fast=not slow,
    )
    await _sleep(*wait)
    await _dismiss_overlays(driver)

    if await _is_blocked(driver):
        if headless:
            raise OzonAccessError(
                "Ozon blocked access on the home page. Run without --headless.",
                url=await driver.current_url,
            )
        logger.warning(
            "Antibot/captcha: up to %d s to complete it in the Chrome window",
            manual_wait,
        )
        deadline = asyncio.get_running_loop().time() + manual_wait
        while asyncio.get_running_loop().time() < deadline:
            await _sleep(2, 3)
            await _dismiss_overlays(driver)
            if not await _is_blocked(driver):
                break
        if await _is_blocked(driver):
            raise OzonAccessError(
                "Failed to pass the check on the Ozon home page.",
                url=await driver.current_url,
            )

    try:
        await wait_for_css(driver, SEARCH_INPUT_CSS, timeout=min(float(element_wait_timeout), 8.0))
    except (TimeoutError, NoSuchElementException):
        logger.debug("Search field did not appear in time; continuing")

    count = await _count_ozon_cookies(driver)
    logger.info("Cookies from Ozon home page: %d", count)
    if count < 2:
        logger.warning("Too few cookies (%d)", count)
    return count


async def prime_session_with_cookies(
    driver: Chrome,
    cookies_path: Path,
    *,
    via_proxy: bool = False,
    page_load_timeout: int | None = None,
    slow: bool = False,
) -> int:
    """
    Быстрый старт: одна загрузка ozon.ru, cookies без refresh, без отдельного прогрева главной.
    """
    path = resolve_cookies_path(cookies_path)
    if not path or not path.exists():
        logger.warning("Cookies file not found: %s", cookies_path)
        return 0

    logger.info("Fast start with cookies: %s", path.name)
    added = await apply_cookies(
        driver,
        path,
        via_proxy=via_proxy,
        page_load_timeout=page_load_timeout,
        page_load_retries=1 if not slow else 2,
        reload=False,
    )
    await _sleep(0.2, 0.4 if slow else 0.3)
    await _dismiss_overlays(driver)

    if await _is_blocked(driver):
        raise OzonAccessError(
            "Ozon blocked access after loading cookies.",
            url=await driver.current_url,
        )

    logger.info("Cookies from file %s: %d", path.name, added)
    return added


async def merge_cookies_from_file(
    driver: Chrome,
    cookies_path: Path,
    *,
    via_proxy: bool = False,
    page_load_timeout: int | None = None,
    page_load_retries: int = 2,
) -> int:
    return await prime_session_with_cookies(
        driver,
        cookies_path,
        via_proxy=via_proxy,
        page_load_timeout=page_load_timeout,
    )
