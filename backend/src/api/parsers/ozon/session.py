from __future__ import annotations

import logging
import random
import time
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

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


def _sleep(min_sec: float, max_sec: float | None = None) -> None:
    time.sleep(random.uniform(min_sec, max_sec or min_sec))


def _is_blocked(driver: WebDriver) -> bool:
    try:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()
        url = driver.current_url.lower()
        blob = f"{url} {body}"
        return any(m in blob for m in BLOCKED_MARKERS)
    except Exception:
        return False


def _dismiss_overlays(driver: WebDriver) -> None:
    for xpath in (
        "//button[contains(.,'OK')]",
        "//button[contains(.,'Понятно')]",
        "//button[contains(.,'Принять')]",
    ):
        try:
            btn = driver.find_element(By.XPATH, xpath)
            if btn.is_displayed():
                btn.click()
                _sleep(0.3, 0.6)
        except Exception:
            continue


def _count_ozon_cookies(driver: WebDriver) -> int:
    return sum(1 for c in driver.get_cookies() if "ozon" in (c.get("domain") or ""))


def warmup_ozon_session(
    driver: WebDriver,
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
    safe_get(
        driver,
        OZON_HOME,
        via_proxy=via_proxy,
        page_load_timeout=page_load_timeout,
        retries=page_load_retries,
    )
    _sleep(*wait)
    _dismiss_overlays(driver)

    if _is_blocked(driver):
        if headless:
            raise OzonAccessError(
                "Ozon заблокировал доступ на главной. Запустите без --headless.",
                url=driver.current_url,
            )
        logger.warning(
            "Антибот/капча — до %d с на прохождение в окне Chrome",
            manual_wait,
        )
        deadline = time.time() + manual_wait
        while time.time() < deadline:
            _sleep(2, 3)
            _dismiss_overlays(driver)
            if not _is_blocked(driver):
                break
        if _is_blocked(driver):
            raise OzonAccessError(
                "Не удалось пройти проверку на главной Ozon.",
                url=driver.current_url,
            )

    try:
        WebDriverWait(driver, element_wait_timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, SEARCH_INPUT_CSS)),
        )
    except Exception:
        logger.debug("Поле поиска не дождались — продолжаем")

    count = _count_ozon_cookies(driver)
    logger.info("Cookies с главной Ozon: %d", count)
    if count < 2:
        logger.warning("Мало cookies (%d)", count)
    return count


def merge_cookies_from_file(
    driver: WebDriver,
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
    added = apply_cookies(
        driver,
        path,
        via_proxy=via_proxy,
        page_load_timeout=page_load_timeout,
        page_load_retries=page_load_retries,
    )
    logger.info("Дополнительно из файла %s: %d cookies", path.name, added)
    return added
