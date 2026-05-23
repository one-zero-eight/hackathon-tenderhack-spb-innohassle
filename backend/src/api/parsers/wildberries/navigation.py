from __future__ import annotations

import logging

from selenium_driverless.webdriver import Chrome

from src.api.parsers.wildberries.exceptions import WildberriesAccessError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 25
FAST_TIMEOUT = 8
DEFAULT_RETRIES = 2


async def safe_get(
    driver: Chrome,
    url: str,
    *,
    page_load_timeout: int | None = None,
    retries: int = DEFAULT_RETRIES,
    fast: bool = False,
    wait_load: bool = True,
) -> None:
    configured = float(page_load_timeout if page_load_timeout is not None else DEFAULT_TIMEOUT)
    timeout = min(configured, float(FAST_TIMEOUT)) if fast else configured
    last_exc: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            await driver.get(url, wait_load=wait_load, timeout=timeout)
            return
        except TimeoutError as exc:
            last_exc = exc
            await _stop_loading(driver)
            logger.warning(
                "Wildberries timeout loading %s (attempt %d/%d)",
                url,
                attempt,
                retries,
            )
        except Exception as exc:
            last_exc = exc
            if "timeout" not in str(exc).lower():
                raise
            await _stop_loading(driver)
            logger.warning(
                "Wildberries load error %s (attempt %d/%d): %s",
                url,
                attempt,
                retries,
                exc,
            )

    raise WildberriesAccessError(f"Failed to open: {url}", url=url) from last_exc


async def _stop_loading(driver: Chrome) -> None:
    try:
        await driver.execute_script("window.stop();")
    except Exception:
        pass
