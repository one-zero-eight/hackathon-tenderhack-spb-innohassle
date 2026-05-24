"""
Location helpers for marketplace parsers.

Resolves a known city/region name to:
  - Wildberries internal ``dest`` ID (negative integer used by search.wb.ru)
  - Yandex Market ``lr`` region ID (Yandex Geobase integer)
  - Ozon delivery city label and ``select_location`` UUID (SERP / composer-api)

The supported locations are intentionally static and shared between
marketplaces. Unknown locations fall back to Moscow.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _MarketplaceLocation:
    aliases: tuple[str, ...]
    wb_dest: int
    ym_region: int
    ozon_city: str


_LOCATIONS: tuple[_MarketplaceLocation, ...] = (
    _MarketplaceLocation(("москва", "moscow"), -1257786, 213, "Москва"),
    _MarketplaceLocation(
        ("санкт-петербург", "петербург", "питер", "saint petersburg", "st. petersburg"),
        -158257,
        2,
        "Санкт-Петербург",
    ),
    _MarketplaceLocation(("новосибирск", "novosibirsk"), -1254478, 65, "Новосибирск"),
    _MarketplaceLocation(("екатеринбург", "yekaterinburg", "ekaterinburg"), -1256682, 54, "Екатеринбург"),
    _MarketplaceLocation(("казань", "kazan", "иннополис", "innopolis"), -2133462, 43, "Казань"),
    _MarketplaceLocation(("нижний новгород", "nizhny novgorod"), -2148313, 47, "Нижний Новгород"),
    _MarketplaceLocation(("челябинск", "chelyabinsk"), -1264706, 56, "Челябинск"),
    _MarketplaceLocation(("самара", "samara"), -2133977, 51, "Самара"),
    _MarketplaceLocation(("уфа", "ufa"), -1336282, 172, "Уфа"),
    _MarketplaceLocation(("ростов-на-дону", "rostov-on-don"), -2145297, 39, "Ростов-на-Дону"),
    _MarketplaceLocation(("краснодар", "krasnodar"), -2140617, 35, "Краснодар"),
    _MarketplaceLocation(("омск", "omsk"), -1255498, 66, "Омск"),
    _MarketplaceLocation(("воронеж", "voronezh"), -2133914, 193, "Воронеж"),
    _MarketplaceLocation(("пермь", "perm"), -2124756, 50, "Пермь"),
    _MarketplaceLocation(("волгоград", "volgograd"), -2133909, 38, "Волгоград"),
    _MarketplaceLocation(("красноярск", "krasnoyarsk"), -1282985, 62, "Красноярск"),
    _MarketplaceLocation(("саратов", "saratov"), -2133919, 194, "Саратов"),
    _MarketplaceLocation(("тюмень", "tyumen"), -1264208, 55, "Тюмень"),
    _MarketplaceLocation(("тольятти", "tolyatti"), -2133978, 51, "Тольятти"),
    _MarketplaceLocation(("иркутск", "irkutsk"), -1257154, 63, "Иркутск"),
    _MarketplaceLocation(("барнаул", "barnaul"), -1255457, 197, "Барнаул"),
    _MarketplaceLocation(("хабаровск", "khabarovsk"), -1273793, 76, "Хабаровск"),
    _MarketplaceLocation(("владивосток", "vladivostok"), -1274204, 75, "Владивосток"),
    _MarketplaceLocation(("ярославль", "yaroslavl"), -2133855, 16, "Ярославль"),
    _MarketplaceLocation(("махачкала", "makhachkala"), -2144509, 28, "Махачкала"),
    _MarketplaceLocation(("томск", "tomsk"), -1255566, 67, "Томск"),
    _MarketplaceLocation(("оренбург", "orenburg"), -1261647, 48, "Оренбург"),
    _MarketplaceLocation(("кемерово", "kemerovo"), -1254838, 64, "Кемерово"),
    _MarketplaceLocation(("новокузнецк", "novokuznetsk"), -1254840, 64, "Новокузнецк"),
    _MarketplaceLocation(("рязань", "ryazan"), -2133856, 11, "Рязань"),
    _MarketplaceLocation(("астрахань", "astrakhan"), -2144258, 37, "Астрахань"),
    _MarketplaceLocation(("набережные челны", "naberezhnye chelny"), -2133479, 43, "Набережные Челны"),
    _MarketplaceLocation(("пенза", "penza"), -2133916, 49, "Пенза"),
    _MarketplaceLocation(("липецк", "lipetsk"), -2133858, 9, "Липецк"),
    _MarketplaceLocation(("тула", "tula"), -2133857, 15, "Тула"),
    _MarketplaceLocation(("киров", "kirov"), -2133476, 46, "Киров"),
    _MarketplaceLocation(("чебоксары", "cheboksary"), -2133480, 45, "Чебоксары"),
    _MarketplaceLocation(("улан-удэ", "ulan-ude"), -1268443, 198, "Улан-Удэ"),
    _MarketplaceLocation(("калининград", "kaliningrad"), -2130032, 22, "Калининград"),
    _MarketplaceLocation(("сочи", "sochi"), -2140649, 239, "Сочи"),
    _MarketplaceLocation(("ставрополь", "stavropol"), -2133988, 36, "Ставрополь"),
    _MarketplaceLocation(("белгород", "belgorod"), -2133911, 4, "Белгород"),
    _MarketplaceLocation(("тверь", "tver"), -2133853, 14, "Тверь"),
    _MarketplaceLocation(("иваново", "ivanovo"), -2133861, 5, "Иваново"),
    _MarketplaceLocation(("брянск", "bryansk"), -2133906, 191, "Брянск"),
)


def _build_lookup(value_attr: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for location in _LOCATIONS:
        value = getattr(location, value_attr)
        for alias in location.aliases:
            if alias in result:
                raise RuntimeError(f"Duplicate marketplace location alias: {alias!r}")
            result[alias] = value
    return result


def _build_str_lookup(value_attr: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for location in _LOCATIONS:
        value = getattr(location, value_attr)
        for alias in location.aliases:
            if alias in result:
                raise RuntimeError(f"Duplicate marketplace location alias: {alias!r}")
            result[alias] = value
    return result


_WB_DEST_MAP = _build_lookup("wb_dest")
_YM_REGION_MAP = _build_lookup("ym_region")
_OZON_CITY_MAP = _build_str_lookup("ozon_city")

_WB_DEFAULT_DEST = _WB_DEST_MAP["москва"]
_YM_DEFAULT_REGION = _YM_REGION_MAP["москва"]
_OZON_DEFAULT_CITY = _OZON_CITY_MAP["москва"]


def _normalize_location(location: str | None) -> str | None:
    if location is None:
        return None
    normalized = location.strip().lower()
    return normalized or None


def resolve_wb_dest(location: str | None) -> int:
    """
    Resolve a city/region name to a Wildberries ``dest`` ID.

    Unknown locations fall back to Moscow.
    """
    key = _normalize_location(location)
    if key is None:
        return _WB_DEFAULT_DEST
    if key in _WB_DEST_MAP:
        return _WB_DEST_MAP[key]

    logger.warning("WB dest not found for %r, falling back to Moscow", location)
    return _WB_DEFAULT_DEST


def resolve_ym_region(location: str | None) -> int:
    """
    Resolve a city/region name to a Yandex Market ``lr`` region ID.

    Unknown locations fall back to Moscow.
    """
    key = _normalize_location(location)
    if key is None:
        return _YM_DEFAULT_REGION
    if key in _YM_REGION_MAP:
        return _YM_REGION_MAP[key]

    logger.warning("YM region not found for %r, falling back to Moscow", location)
    return _YM_DEFAULT_REGION


def resolve_ozon_city(location: str | None) -> str:
    """
    Resolve a city/region name to an Ozon delivery city label.

    Unknown locations fall back to Moscow.
    """
    key = _normalize_location(location)
    if key is None:
        return _OZON_DEFAULT_CITY
    if key in _OZON_CITY_MAP:
        return _OZON_CITY_MAP[key]

    logger.warning("Ozon city not found for %r, falling back to Moscow", location)
    return _OZON_DEFAULT_CITY


def resolve_ozon_select_location(location: str | None) -> str:
    """
    Resolve ``select_location`` UUID for Ozon HTTP/SERP requests.

    Uses static map for known aliases; unknown locations fall back to Moscow.
    """
    from src.api.parsers.ozon.location import DEFAULT_OZON_SELECT_LOCATION, lookup_ozon_select_location_key

    key = _normalize_location(location)
    resolved = lookup_ozon_select_location_key(key)
    if resolved:
        return resolved
    if key is not None:
        logger.warning(
            "Ozon select_location not found for %r, falling back to Moscow",
            location,
        )
    return DEFAULT_OZON_SELECT_LOCATION
