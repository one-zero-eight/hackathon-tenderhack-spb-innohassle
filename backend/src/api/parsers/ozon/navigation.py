from __future__ import annotations

import logging

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver

from src.api.parsers.ozon.exceptions import OzonAccessError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 90
PROXY_TIMEOUT = 180
DEFAULT_SCRIPT_TIMEOUT = 60
PROXY_SCRIPT_TIMEOUT = 90
DEFAULT_ELEMENT_WAIT = 45
DEFAULT_RETRIES = 4


def configure_timeouts(
    driver: WebDriver,
    *,
    via_proxy: bool,
    page_load_timeout: int | None = None,
) -> None:
    load_timeout = page_load_timeout or (PROXY_TIMEOUT if via_proxy else DEFAULT_TIMEOUT)
    script_timeout = PROXY_SCRIPT_TIMEOUT if via_proxy else DEFAULT_SCRIPT_TIMEOUT
    driver.set_page_load_timeout(load_timeout)
    driver.set_script_timeout(script_timeout)


def safe_get(
    driver: WebDriver,
    url: str,
    *,
    via_proxy: bool = False,
    page_load_timeout: int | None = None,
    retries: int = DEFAULT_RETRIES,
) -> None:
    configure_timeouts(driver, via_proxy=via_proxy, page_load_timeout=page_load_timeout)
    last_exc: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            driver.get(url)
            return
        except TimeoutException as exc:
            last_exc = exc
            _stop_loading(driver)
            logger.warning(
                "Таймаут загрузки %s (попытка %d/%d)%s",
                url,
                attempt,
                retries,
                " — прокси может быть медленным" if via_proxy else "",
            )
        except WebDriverException as exc:
            last_exc = exc
            if "timeout" not in str(exc).lower():
                raise
            _stop_loading(driver)
            logger.warning("Ошибка загрузки %s (попытка %d/%d): %s", url, attempt, retries, exc)

    hint = (
        "Проверьте прокси (скорость, RU IP), попробуйте --slow или http:// вместо socks5://."
        if via_proxy
        else "Попробуйте --slow или меньший -n."
    )
    raise OzonAccessError(f"Не удалось открыть: {url}. {hint}", url=url) from last_exc


def _stop_loading(driver: WebDriver) -> None:
    try:
        driver.execute_script("window.stop();")
    except Exception:
        pass
