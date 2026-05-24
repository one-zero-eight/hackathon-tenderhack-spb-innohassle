from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from cloakbrowser import launch_context_async, launch_persistent_context_async
from playwright.async_api import BrowserContext, Page

from proxy_bridge import bridge_manager, needs_socks_proxy_bridge

logger = logging.getLogger(__name__)

SEARCH_ROOT = Path(__file__).resolve().parent.parent
VIEWPORT = {"width": 1440, "height": 900}
DOCKER_PROFILES_ROOT = Path("/app/data/cloak-profiles")
LOCAL_PROFILES_ROOT = SEARCH_ROOT / "data" / "cloak-profiles"


def cloak_profiles_root() -> Path:
    if env_dir := os.getenv("CLOAK_PROFILES_DIR"):
        candidates = [Path(env_dir).expanduser()]
    else:
        candidates = [DOCKER_PROFILES_ROOT, LOCAL_PROFILES_ROOT]

    for root in candidates:
        try:
            root.mkdir(parents=True, exist_ok=True)
            return root
        except OSError:
            logger.debug("CloakBrowser profiles dir not writable: %s", root)
    raise RuntimeError("Could not create a writable CloakBrowser profiles directory")


def new_pool_profile_dir(prefix: str) -> Path:
    profile = cloak_profiles_root() / f"{prefix}-{uuid.uuid4().hex[:10]}"
    profile.mkdir(parents=True, exist_ok=True)
    return profile


@dataclass(frozen=True)
class CloakSessionConfig:
    headless: bool = True
    proxy: str | None = None
    geoip: bool = True
    humanize: bool = False
    user_data_dir: Path | None = None
    locale: str = "ru-RU"
    timezone: str = "Europe/Moscow"


def _proxy_log_label(proxy: str | None) -> str:
    if proxy is None:
        return "none"
    parsed = urlparse(proxy)
    host = parsed.hostname or "?"
    port = f":{parsed.port}" if parsed.port else ""
    if parsed.username or "@" in proxy:
        return f"{parsed.scheme or '?'}://***@{host}{port}"
    return f"{parsed.scheme or '?'}://{host}{port}"


def _launch_kwargs(
    config: CloakSessionConfig,
    *,
    proxy: str | None,
    use_geoip: bool | None = None,
) -> dict[str, object]:
    geoip = config.geoip if use_geoip is None else use_geoip
    kwargs: dict[str, object] = {
        "headless": config.headless,
        "viewport": VIEWPORT,
        "locale": config.locale,
        "timezone": config.timezone,
        "humanize": config.humanize,
    }
    if proxy is not None:
        kwargs["proxy"] = proxy
        if geoip:
            kwargs["geoip"] = True
    return kwargs


async def _resolve_launch_proxy(config: CloakSessionConfig) -> tuple[str | None, str | None]:
    if not config.proxy:
        return None, None
    if needs_socks_proxy_bridge(config.proxy):
        local_http = await bridge_manager.acquire(config.proxy)
        logger.info(
            "CloakBrowser SOCKS5 bridge %s -> %s",
            _proxy_log_label(config.proxy),
            local_http,
        )
        return local_http, config.proxy
    return config.proxy, None


async def _open_session(
    config: CloakSessionConfig,
    *,
    proxy: str | None,
    use_geoip: bool | None,
) -> tuple[BrowserContext, Page]:
    launch_kwargs = _launch_kwargs(config, proxy=proxy, use_geoip=use_geoip)
    if config.user_data_dir is not None:
        profile_dir = str(config.user_data_dir.resolve())
        logger.info(
            "CloakBrowser persistent profile %s (proxy=%s)",
            profile_dir,
            _proxy_log_label(proxy),
        )
        context = await launch_persistent_context_async(profile_dir, **launch_kwargs)
    else:
        logger.info("CloakBrowser context (proxy=%s)", _proxy_log_label(proxy))
        context = await launch_context_async(**launch_kwargs)

    page = context.pages[0] if context.pages else await context.new_page()
    return context, page


async def open_cloak_session(config: CloakSessionConfig) -> tuple[BrowserContext, Page, str | None]:
    launch_proxy, bridge_upstream = await _resolve_launch_proxy(config)
    use_geoip = config.geoip and bridge_upstream is None
    try:
        context, page = await _open_session(config, proxy=launch_proxy, use_geoip=use_geoip)
        return context, page, bridge_upstream
    except Exception:
        if bridge_upstream:
            await bridge_manager.release(bridge_upstream)
        raise


async def close_cloak_session(
    context: BrowserContext | None,
    *,
    bridge_upstream: str | None = None,
) -> None:
    if context is None:
        return
    try:
        await context.close()
    except Exception as exc:
        logger.warning("CloakBrowser context close failed: %s", exc)
    if bridge_upstream:
        await bridge_manager.release(bridge_upstream)
