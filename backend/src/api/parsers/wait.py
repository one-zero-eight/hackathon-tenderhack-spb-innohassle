from __future__ import annotations

import asyncio
from typing import Any

from selenium_driverless.types.by import By
from selenium_driverless.types.webelement import NoSuchElementException, WebElement
from selenium_driverless.webdriver import Chrome

_STALE_PAGE_MARKERS = (
    "reloaded",
    "object deleted",
    "globalthis",
)


def is_stale_page_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _STALE_PAGE_MARKERS)


async def safe_execute_script(
    driver: Chrome,
    script: str,
    *args: object,
    retries: int = 4,
    retry_delay: float = 0.25,
) -> Any:
    """Повтор при гонке навигации (Page or Frame has been reloaded…)."""
    last_exc: BaseException | None = None
    for attempt in range(1, retries + 1):
        try:
            return await driver.execute_script(script, *args)
        except Exception as exc:
            last_exc = exc
            if not is_stale_page_error(exc) or attempt >= retries:
                raise
            await asyncio.sleep(retry_delay)
    if last_exc:
        raise last_exc
    raise RuntimeError("safe_execute_script failed without exception")


async def wait_for_element(
    driver: Chrome,
    by: str,
    value: str,
    *,
    timeout: float = 15,
    poll_interval: float = 0.3,
) -> WebElement:
    """
    Ждёт элемент с asyncio.sleep между попытками.

    selenium-driverless find_element() крутит tight loop без sleep — блокирует event loop.
    """
    deadline = asyncio.get_running_loop().time() + timeout
    last_error: Exception | None = None

    while asyncio.get_running_loop().time() < deadline:
        try:
            elements = await driver.find_elements(by, value, timeout=1)
            if elements:
                return elements[0]
        except Exception as exc:
            last_error = exc
            if is_stale_page_error(exc):
                await asyncio.sleep(poll_interval)
                continue
        await asyncio.sleep(poll_interval)

    if last_error:
        raise TimeoutError(f"Element not found: {by}={value!r}") from last_error
    raise NoSuchElementException(f"Element not found: {by}={value!r}")


async def wait_for_css(
    driver: Chrome,
    selector: str,
    *,
    timeout: float = 15,
    poll_interval: float = 0.3,
) -> WebElement:
    return await wait_for_element(
        driver,
        By.CSS_SELECTOR,
        selector,
        timeout=timeout,
        poll_interval=poll_interval,
    )


async def wait_for_script_true(
    driver: Chrome,
    script: str,
    *,
    timeout: float = 8,
    poll_interval: float = 0.15,
) -> None:
    """Ждёт условие в DOM; execute_script с retry при reload страницы."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        try:
            if await safe_execute_script(driver, script):
                return
        except Exception as exc:
            if not is_stale_page_error(exc):
                raise
        await asyncio.sleep(poll_interval)
    raise TimeoutError(f"Condition not met within {timeout}s")
