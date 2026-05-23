from __future__ import annotations

import json
import logging
from pathlib import Path

from playwright.async_api import BrowserContext, Page

from src.api.parsers.playwright_page import goto

logger = logging.getLogger(__name__)

OZON_HOME = "https://www.ozon.ru/"
OZON_ORIGINS = ("https://www.ozon.ru", "https://ozon.ru")


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
    """True when cookies.json contains a non-empty __Secure-user-id."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get("cookies", data) if isinstance(data, dict) else data
        if not isinstance(raw, list):
            return False
        for item in raw:
            if item.get("name") == "__Secure-user-id":
                user_id = item.get("value")
                return bool(user_id and str(user_id) not in ("0", ""))
        return False
    except Exception:
        return False


async def browser_has_ozon_session(context: BrowserContext) -> bool:
    for origin in OZON_ORIGINS:
        try:
            for cookie in await context.cookies(origin):
                if cookie.get("name") == "__Secure-user-id":
                    value = cookie.get("value")
                    return bool(value and str(value) not in ("0", ""))
        except Exception:
            continue
    return False


def load_cookies_file(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(path)

    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("cookies", data) if isinstance(data, dict) else data
    if not isinstance(raw, list):
        raise ValueError("cookies.json: expected a list (Cookie-Editor format)")

    cookies: list[dict] = []
    for item in raw:
        name = item.get("name")
        value = item.get("value")
        if not name or value is None:
            continue
        entry: dict = {
            "name": name,
            "value": str(value),
            "domain": item.get("domain", ".ozon.ru"),
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


async def apply_cookies_to_context(
    context: BrowserContext,
    page: Page,
    cookies_path: Path,
    *,
    page_load_timeout: int = 20,
) -> tuple[int, bool]:
    """Load cookies.json into a CloakBrowser context (domain must be opened first)."""
    cookies = load_cookies_file(cookies_path)
    await goto(
        page,
        OZON_HOME,
        timeout_sec=float(page_load_timeout),
        wait_until="commit",
        retries=2,
    )
    try:
        await context.clear_cookies()
    except Exception:
        pass
    await context.add_cookies(cookies)
    await page.reload(wait_until="domcontentloaded", timeout=int(page_load_timeout * 1000))
    session_ok = await browser_has_ozon_session(context)
    logger.info(
        "Ozon cookies applied: %d from %s (session_cookie_in_browser=%s)",
        len(cookies),
        cookies_path.name,
        session_ok,
    )
    if cookies_file_has_session(cookies_path) and not session_ok:
        logger.warning(
            "Ozon cookies.json has __Secure-user-id but browser did not receive it — "
            "check Cookie-Editor export or clear data/cloak-profiles/ozon-* and restart",
        )
    return len(cookies), session_ok
