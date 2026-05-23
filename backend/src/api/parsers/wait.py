from __future__ import annotations

import asyncio

from selenium_driverless.types.by import By
from selenium_driverless.types.webelement import NoSuchElementException, WebElement
from selenium_driverless.webdriver import Chrome


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
            elements = await driver.find_elements(by, value, timeout=2)
            if elements:
                return elements[0]
        except Exception as exc:
            last_error = exc
        await asyncio.sleep(poll_interval)

    if last_error:
        raise TimeoutError(f"Element not found: {by}={value!r}") from last_error
    raise NoSuchElementException(f"Element not found: {by}={value!r}")


async def wait_for_css(driver: Chrome, selector: str, *, timeout: float = 15) -> WebElement:
    return await wait_for_element(driver, By.CSS_SELECTOR, selector, timeout=timeout)
