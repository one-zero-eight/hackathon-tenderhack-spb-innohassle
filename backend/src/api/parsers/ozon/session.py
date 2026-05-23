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
from src.api.parsers.ozon.navigation import DEFAULT_ELEMENT_WAIT, DEFAULT_RETRIES, safe_get

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
            btn = await driver.find_element(By.XPATH, xpath, timeout=2)
            if await btn.is_visible():
                await btn.click()
                await _sleep(0.3, 0.6)
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
    page_load_retries: int = DEFAULT_RETRIES,
) -> int:
    wait = (8.0, 12.0) if slow or via_proxy else (2.5, 4.0)
    manual_wait = 90 if via_proxy and not headless else (60 if not headless else 45)

    logger.info("Прогрев: открываю %s", OZON_HOME)
    await safe_get(
        driver,
        OZON_HOME,
        via_proxy=via_proxy,
        page_load_timeout=page_load_timeout,
        retries=page_load_retries,
    )
    await _sleep(*wait)
    await _dismiss_overlays(driver)

    if await _is_blocked(driver):
        if headless:
            raise OzonAccessError(
                "Ozon заблокировал доступ на главной. Запустите без --headless.",
                url=await driver.current_url,
            )
        logger.warning(
            "Антибот/капча — до %d с на прохождение в окне Chrome",
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
                "Не удалось пройти проверку на главной Ozon.",
                url=await driver.current_url,
            )

    try:
        await driver.find_element(By.CSS_SELECTOR, SEARCH_INPUT_CSS, timeout=element_wait_timeout)
    except (TimeoutError, NoSuchElementException):
        logger.debug("Поле поиска не дождались — продолжаем")

    count = await _count_ozon_cookies(driver)
    logger.info("Cookies с главной Ozon: %d", count)
    if count < 2:
        logger.warning("Мало cookies (%d)", count)
    return count


async def merge_cookies_from_file(
    driver: Chrome,
    cookies_path: Path,
    *,
    via_proxy: bool = False,
    page_load_timeout: int | None = None,
    page_load_retries: int = DEFAULT_RETRIES,
) -> int:
    path = resolve_cookies_path(cookies_path)
    if not path or not path.exists():
        logger.warning("Файл cookies не найден: %s", cookies_path)
        return 0
    added = await apply_cookies(
        driver,
        path,
        via_proxy=via_proxy,
        page_load_timeout=page_load_timeout,
        page_load_retries=page_load_retries,
    )
    logger.info("Дополнительно из файла %s: %d cookies", path.name, added)
    return added
