from __future__ import annotations

import asyncio
import logging

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


async def goto(
    page: Page,
    url: str,
    *,
    timeout_sec: float,
    wait_until: str = "domcontentloaded",
    retries: int = 1,
    retry_wait_until: str | None = "commit",
) -> None:
    timeout_ms = int(timeout_sec * 1000)
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        load_until = wait_until
        if attempt > 1 and retry_wait_until:
            load_until = retry_wait_until
        try:
            await page.goto(url, timeout=timeout_ms, wait_until=load_until)
            return
        except PlaywrightTimeoutError as exc:
            last_exc = exc
            logger.warning(
                "Timeout loading %s (attempt %d/%d, wait_until=%s)",
                url,
                attempt,
                retries,
                load_until,
            )
        except Exception as exc:
            if "timeout" not in str(exc).lower():
                raise
            last_exc = exc
            logger.warning(
                "Load error %s (attempt %d/%d): %s",
                url,
                attempt,
                retries,
                exc,
            )
    if last_exc:
        raise TimeoutError(f"Не удалось открыть: {url}") from last_exc


async def evaluate(page: Page, script: str, *args: object) -> object:
    if args:
        return await page.evaluate(script, *args)
    return await page.evaluate(script)


async def wait_for_function(
    page: Page,
    script: str,
    *,
    timeout_sec: float,
    poll_interval_sec: float = 0.2,
) -> None:
    timeout_ms = int(timeout_sec * 1000)
    try:
        await page.wait_for_function(script, timeout=timeout_ms, polling=poll_interval_sec * 1000)
    except PlaywrightTimeoutError as exc:
        raise TimeoutError(f"Condition not met within {timeout_sec}s") from exc


async def page_blob(page: Page) -> str:
    title = (await page.title()).lower()
    body = await evaluate(page, "document.body ? document.body.innerText : ''")
    return f"{title} {(body or '').lower()}"


async def dismiss_buttons(page: Page, labels: tuple[str, ...]) -> None:
    for label in labels:
        locator = page.get_by_role("button", name=label)
        try:
            if await locator.count() > 0:
                await locator.first.click(timeout=1500)
                await asyncio.sleep(0.25)
        except Exception:
            continue
