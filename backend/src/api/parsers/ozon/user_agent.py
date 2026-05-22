from __future__ import annotations

import logging

from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

# Chrome на desktop — новый UA на каждый вызов pick_user_agent()
_ua = UserAgent(
    browsers=["Chrome"],
    os=["Mac OS X", "Windows"],
    platforms="desktop",
    min_version=120.0,
)

_FALLBACK = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def pick_user_agent() -> str:
    return _ua.random
