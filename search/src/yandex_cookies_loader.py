from __future__ import annotations

import json
import logging
from pathlib import Path

from playwright.async_api import BrowserContext, Page

logger = logging.getLogger(__name__)

YA_RU_URL = "https://ya.ru/"
YANDEX_ORIGINS = ("https://ya.ru", "https://yandex.ru", "https://www.yandex.ru")


def _normalize_same_site(value: object) -> str | None:
    if value is None:
        return None
    raw = str(value).strip().lower().replace("-", "_")
    if raw in ("", "null", "unspecified"):
        return None
    if raw in ("no_restriction", "none"):
        return "None"
    if raw == "lax":
        return "Lax"
    if raw == "strict":
        return "Strict"
    return None


def cookies_file_has_session(path: Path) -> bool:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get("cookies", data) if isinstance(data, dict) else data
        if not isinstance(raw, list):
            return False
        for item in raw:
            if item.get("name") == "Session_id":
                value = item.get("value")
                return bool(value and str(value).strip())
        return False
    except Exception:
        return False


async def browser_has_yandex_session(context: BrowserContext) -> bool:
    for origin in YANDEX_ORIGINS:
        try:
            for cookie in await context.cookies(origin):
                if cookie.get("name") == "Session_id":
                    value = cookie.get("value")
                    return bool(value and str(value).strip())
        except Exception:
            continue
    return False


def load_yandex_cookies_file(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"Yandex cookies file not found: {path}. "
            "Copy yandex_cookies.example.json to yandex_cookies.json and fill in your cookies."
        )

    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("cookies", data) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        raise ValueError(f"{path.name}: expected a Cookie-Editor list export")

    cookies: list[dict] = []
    for item in raw:
        name = item.get("name")
        value = item.get("value")
        if not name or value is None:
            continue

        domain = item.get("domain")
        if domain and "yandex" not in str(domain):
            continue

        entry: dict = {
            "name": name,
            "value": str(value),
            "domain": domain or ".yandex.ru",
            "path": item.get("path", "/"),
        }
        if item.get("secure"):
            entry["secure"] = True
        if item.get("httpOnly"):
            entry["httpOnly"] = True

        same_site = _normalize_same_site(item.get("sameSite"))
        if same_site:
            entry["sameSite"] = same_site

        expires = item.get("expirationDate", item.get("expires"))
        if expires is not None:
            try:
                entry["expires"] = int(float(expires))
            except (TypeError, ValueError):
                pass

        cookies.append(entry)

    return cookies


async def _open_yandex_home(page: Page, *, timeout_ms: int) -> None:
    last_error: Exception | None = None
    for wait_until in ("domcontentloaded", "commit"):
        try:
            await page.goto(YA_RU_URL, wait_until=wait_until, timeout=timeout_ms)
            return
        except Exception as exc:
            last_error = exc
            message = str(exc)
            if wait_until == "domcontentloaded" and (
                "ERR_ABORTED" in message or "frame was detached" in message
            ):
                continue
            raise
    if last_error is not None:
        raise last_error


async def apply_yandex_cookies_to_context(
    context: BrowserContext,
    page: Page,
    cookies_path: Path,
    *,
    page_load_timeout_ms: int = 30_000,
) -> tuple[int, bool]:
    cookies = load_yandex_cookies_file(cookies_path)
    await _open_yandex_home(page, timeout_ms=page_load_timeout_ms)
    try:
        await context.clear_cookies()
    except Exception:
        pass
    await context.add_cookies(cookies)
    try:
        await _open_yandex_home(page, timeout_ms=page_load_timeout_ms)
    except Exception as exc:
        logger.warning("Yandex post-cookie navigation failed: %s", exc)

    session_ok = await browser_has_yandex_session(context)
    logger.info(
        "Yandex cookies applied: %d from %s (session_cookie_in_browser=%s)",
        len(cookies),
        cookies_path.name,
        session_ok,
    )
    if cookies_file_has_session(cookies_path) and not session_ok:
        logger.warning(
            "yandex_cookies.json has Session_id but browser did not receive it — "
            "re-export cookies from Cookie-Editor or clear data/cloak-profiles/yandex-*",
        )
    return len(cookies), session_ok
