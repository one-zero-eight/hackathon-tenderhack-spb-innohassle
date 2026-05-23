"""
Geocoder helpers for marketplace parsers.

Resolves a free-text city/region name to:
  - Wildberries internal ``dest`` ID (negative integer used by search.wb.ru)
  - Yandex Market ``lr`` region ID (Yandex Geobase integer)

Resolution strategy (no external third-party APIs):
  1. Case-insensitive static lookup table (instant, no network).
  2. Local Nominatim HTTP API (running as a Docker container on the same
     Docker network).  The base URL is taken from ``api_settings.nominatim_url``.
  3. Fall back to Moscow defaults when resolution fails.
"""

from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Wildberries  dest IDs
# Captured via browser dev-tools (Network tab → search.wb.ru request URL)
# after changing the delivery city on wildberries.ru.
# ---------------------------------------------------------------------------
_WB_DEST_MAP: dict[str, int] = {
    "москва": -1257786,
    "moscow": -1257786,
    "санкт-петербург": -158257,
    "петербург": -158257,
    "питер": -158257,
    "saint petersburg": -158257,
    "st. petersburg": -158257,
    "новосибирск": -1254478,
    "novosibirsk": -1254478,
    "екатеринбург": -1256682,
    "yekaterinburg": -1256682,
    "ekaterinburg": -1256682,
    "казань": -2133462,
    "kazan": -2133462,
    "нижний новгород": -2148313,
    "nizhny novgorod": -2148313,
    "челябинск": -1264706,
    "chelyabinsk": -1264706,
    "самара": -2133977,
    "samara": -2133977,
    "уфа": -1336282,
    "ufa": -1336282,
    "ростов-на-дону": -2145297,
    "rostov-on-don": -2145297,
    "краснодар": -2140617,
    "krasnodar": -2140617,
    "омск": -1255498,
    "omsk": -1255498,
    "воронеж": -2133914,
    "voronezh": -2133914,
    "пермь": -2124756,
    "perm": -2124756,
    "волгоград": -2133909,
    "volgograd": -2133909,
    "красноярск": -1282985,
    "krasnoyarsk": -1282985,
    "саратов": -2133919,
    "saratov": -2133919,
    "тюмень": -1264208,
    "tyumen": -1264208,
    "тольятти": -2133978,
    "tolyatti": -2133978,
    "иркутск": -1257154,
    "irkutsk": -1257154,
    "барнаул": -1255457,
    "barnaul": -1255457,
    "хабаровск": -1273793,
    "khabarovsk": -1273793,
    "владивосток": -1274204,
    "vladivostok": -1274204,
    "ярославль": -2133855,
    "yaroslavl": -2133855,
    "махачкала": -2144509,
    "makhachkala": -2144509,
    "томск": -1255566,
    "tomsk": -1255566,
    "оренбург": -1261647,
    "orenburg": -1261647,
    "кемерово": -1254838,
    "kemerovo": -1254838,
    "новокузнецк": -1254840,
    "novokuznetsk": -1254840,
    "рязань": -2133856,
    "ryazan": -2133856,
    "астрахань": -2144258,
    "astrakhan": -2144258,
    "набережные челны": -2133479,
    "naberezhnye chelny": -2133479,
    "пенза": -2133916,
    "penza": -2133916,
    "липецк": -2133858,
    "lipetsk": -2133858,
    "тула": -2133857,
    "tula": -2133857,
    "киров": -2133476,
    "kirov": -2133476,
    "чебоксары": -2133480,
    "cheboksary": -2133480,
    "улан-удэ": -1268443,
    "ulan-ude": -1268443,
    "калининград": -2130032,
    "kaliningrad": -2130032,
    "балашиха": -1257767,
    "balashikha": -1257767,
    "сочи": -2140649,
    "sochi": -2140649,
    "ставрополь": -2133988,
    "stavropol": -2133988,
    "белгород": -2133911,
    "belgorod": -2133911,
    "тверь": -2133853,
    "tver": -2133853,
    "иваново": -2133861,
    "ivanovo": -2133861,
    "брянск": -2133906,
    "bryansk": -2133906,
}

_WB_DEFAULT_DEST = -1257786  # Moscow


# ---------------------------------------------------------------------------
# Yandex Market  lr (region) IDs  — Yandex Geobase integers
# ---------------------------------------------------------------------------
_YM_REGION_MAP: dict[str, int] = {
    "москва": 213,
    "moscow": 213,
    "санкт-петербург": 2,
    "петербург": 2,
    "питер": 2,
    "saint petersburg": 2,
    "st. petersburg": 2,
    "новосибирск": 65,
    "novosibirsk": 65,
    "екатеринбург": 54,
    "yekaterinburg": 54,
    "ekaterinburg": 54,
    "казань": 43,
    "kazan": 43,
    "нижний новгород": 47,
    "nizhny novgorod": 47,
    "челябинск": 56,
    "chelyabinsk": 56,
    "самара": 51,
    "samara": 51,
    "уфа": 172,
    "ufa": 172,
    "ростов-на-дону": 39,
    "rostov-on-don": 39,
    "краснодар": 35,
    "krasnodar": 35,
    "омск": 66,
    "omsk": 66,
    "воронеж": 193,
    "voronezh": 193,
    "пермь": 50,
    "perm": 50,
    "волгоград": 38,
    "volgograd": 38,
    "красноярск": 62,
    "krasnoyarsk": 62,
    "саратов": 194,
    "saratov": 194,
    "тюмень": 55,
    "tyumen": 55,
    "тольятти": 51,
    "tolyatti": 51,
    "иркутск": 63,
    "irkutsk": 63,
    "барнаул": 197,
    "barnaul": 197,
    "хабаровск": 76,
    "khabarovsk": 76,
    "владивосток": 75,
    "vladivostok": 75,
    "ярославль": 16,
    "yaroslavl": 16,
    "томск": 67,
    "tomsk": 67,
    "оренбург": 48,
    "orenburg": 48,
    "кемерово": 64,
    "kemerovo": 64,
    "новокузнецк": 64,
    "novokuznetsk": 64,
    "рязань": 11,
    "ryazan": 11,
    "астрахань": 37,
    "astrakhan": 37,
    "набережные челны": 43,
    "naberezhnye chelny": 43,
    "пенза": 49,
    "penza": 49,
    "липецк": 9,
    "lipetsk": 9,
    "тула": 15,
    "tula": 15,
    "киров": 46,
    "kirov": 46,
    "чебоксары": 45,
    "cheboksary": 45,
    "улан-удэ": 198,
    "ulan-ude": 198,
    "калининград": 22,
    "kaliningrad": 22,
    "махачкала": 28,
    "makhachkala": 28,
    "владикавказ": 33,
    "vladikavkaz": 33,
    "сочи": 239,
    "sochi": 239,
    "ставрополь": 36,
    "stavropol": 36,
    "белгород": 4,
    "belgorod": 4,
    "курск": 8,
    "kursk": 8,
    "иваново": 5,
    "ivanovo": 5,
    "брянск": 191,
    "bryansk": 191,
    "тверь": 14,
    "tver": 14,
    "россия": 225,
    "russia": 225,
}

_YM_DEFAULT_REGION = 213  # Moscow


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _nominatim_name_parts(location: str, nominatim_url: str) -> list[str]:
    """
    Query the local Nominatim container and return the comma-separated parts
    of the best-matching display name (lowercased).

    Returns an empty list on any error or when no results are found.
    """
    try:
        resp = requests.get(
            f"{nominatim_url.rstrip('/')}/search",
            params={"q": location, "format": "json", "limit": 1, "accept-language": "ru"},
            headers={"User-Agent": "TenderHack-Backend/1.0"},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        if data:
            return [part.strip().lower() for part in data[0].get("display_name", "").split(",")]
    except Exception as exc:
        logger.debug("Nominatim lookup failed for %r: %s", location, exc)
    return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_wb_dest(location: str | None, nominatim_url: str) -> int:
    """
    Resolve a city/region name to a Wildberries ``dest`` ID.

    Args:
        location:      Free-text city name.  ``None`` → Moscow default.
        nominatim_url: Base URL of the local Nominatim service.

    Returns:
        Integer dest ID (negative) understood by search.wb.ru.
    """
    if location is None:
        return _WB_DEFAULT_DEST

    key = location.strip().lower()
    if key in _WB_DEST_MAP:
        return _WB_DEST_MAP[key]

    # Fallback: try to normalise via local Nominatim
    for part in _nominatim_name_parts(location, nominatim_url):
        if part in _WB_DEST_MAP:
            logger.debug("WB dest resolved %r → %r via Nominatim", location, part)
            return _WB_DEST_MAP[part]

    logger.warning("WB dest not found for %r, falling back to Moscow", location)
    return _WB_DEFAULT_DEST


def resolve_ym_region(location: str | None, nominatim_url: str) -> int:
    """
    Resolve a city/region name to a Yandex Market ``lr`` region ID.

    Args:
        location:      Free-text city name.  ``None`` → Moscow default.
        nominatim_url: Base URL of the local Nominatim service.

    Returns:
        Integer region ID understood by market.yandex.ru as the ``lr`` param.
    """
    if location is None:
        return _YM_DEFAULT_REGION

    key = location.strip().lower()
    if key in _YM_REGION_MAP:
        return _YM_REGION_MAP[key]

    # Fallback: try to normalise via local Nominatim
    for part in _nominatim_name_parts(location, nominatim_url):
        if part in _YM_REGION_MAP:
            logger.debug("YM region resolved %r → %r via Nominatim", location, part)
            return _YM_REGION_MAP[part]

    logger.warning("YM region not found for %r, falling back to Moscow", location)
    return _YM_DEFAULT_REGION
