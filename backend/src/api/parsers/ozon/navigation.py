from __future__ import annotations

import logging

from selenium_driverless.webdriver import Chrome

from src.api.parsers.ozon.exceptions import OzonAccessError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 90
PROXY_TIMEOUT = 180
FAST_NAVIGATION_CAP = 8
DEFAULT_ELEMENT_WAIT = 45
DEFAULT_RETRIES = 4


def _load_timeout(*, via_proxy: bool, page_load_timeout: int | None) -> float:
    if page_load_timeout is not None:
        return float(page_load_timeout)
    return float(PROXY_TIMEOUT if via_proxy else DEFAULT_TIMEOUT)


def effective_navigation_timeout(
    *,
    via_proxy: bool,
    page_load_timeout: int | None,
    fast: bool = False,
) -> float:
    """Ограничивает таймаут навигации, чтобы не ждать 180 с из settings при обычном поиске."""
    timeout = _load_timeout(via_proxy=via_proxy, page_load_timeout=page_load_timeout)
    if fast:
        return min(timeout, float(FAST_NAVIGATION_CAP))
    return timeout


async def safe_get(
    driver: Chrome,
    url: str,
    *,
    via_proxy: bool = False,
    page_load_timeout: int | None = None,
    retries: int = DEFAULT_RETRIES,
    fast: bool = False,
    wait_load: bool = True,
) -> None:
    timeout = effective_navigation_timeout(
        via_proxy=via_proxy,
        page_load_timeout=page_load_timeout,
        fast=fast,
    )
    last_exc: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            await driver.get(url, wait_load=wait_load, timeout=timeout)
            return
        except TimeoutError as exc:
            last_exc = exc
            await _stop_loading(driver)
            logger.warning(
                "Loading %s timed out (attempt %d/%d)%s",
                url,
                attempt,
                retries,
                "; proxy may be slow" if via_proxy else "",
            )
        except Exception as exc:
            last_exc = exc
            if "timeout" not in str(exc).lower():
                raise
            await _stop_loading(driver)
            logger.warning("Loading %s failed (attempt %d/%d): %s", url, attempt, retries, exc)

    hint = (
        "Check the proxy (speed, RU IP), try --slow, or use http:// instead of socks5://."
        if via_proxy
        else "Try --slow or a smaller -n."
    )
    raise OzonAccessError(f"Failed to open: {url}. {hint}", url=url) from last_exc


async def _stop_loading(driver: Chrome) -> None:
    try:
        await driver.execute_script("window.stop();")
    except Exception:
        pass
