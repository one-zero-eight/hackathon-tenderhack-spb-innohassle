"""
Location helpers for marketplace parsers.

Resolves a known city/region name to:
  - Wildberries internal ``dest`` ID (negative integer used by search.wb.ru)
  - Yandex Market ``lr`` region ID (Yandex Geobase integer)

The supported locations are intentionally static and shared between both
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


_LOCATIONS: tuple[_MarketplaceLocation, ...] = (
    _MarketplaceLocation(("москва", "moscow"), -1257786, 213),
    _MarketplaceLocation(
        ("санкт-петербург", "петербург", "питер", "saint petersburg", "st. petersburg"),
        -158257,
        2,
    ),
    _MarketplaceLocation(("новосибирск", "novosibirsk"), -1254478, 65),
    _MarketplaceLocation(("екатеринбург", "yekaterinburg", "ekaterinburg"), -1256682, 54),
    _MarketplaceLocation(("казань", "kazan", "иннополис", "innopolis"), -2133462, 43),
    _MarketplaceLocation(("нижний новгород", "nizhny novgorod"), -2148313, 47),
    _MarketplaceLocation(("челябинск", "chelyabinsk"), -1264706, 56),
    _MarketplaceLocation(("самара", "samara"), -2133977, 51),
    _MarketplaceLocation(("уфа", "ufa"), -1336282, 172),
    _MarketplaceLocation(("ростов-на-дону", "rostov-on-don"), -2145297, 39),
    _MarketplaceLocation(("краснодар", "krasnodar"), -2140617, 35),
    _MarketplaceLocation(("омск", "omsk"), -1255498, 66),
    _MarketplaceLocation(("воронеж", "voronezh"), -2133914, 193),
    _MarketplaceLocation(("пермь", "perm"), -2124756, 50),
    _MarketplaceLocation(("волгоград", "volgograd"), -2133909, 38),
    _MarketplaceLocation(("красноярск", "krasnoyarsk"), -1282985, 62),
    _MarketplaceLocation(("саратов", "saratov"), -2133919, 194),
    _MarketplaceLocation(("тюмень", "tyumen"), -1264208, 55),
    _MarketplaceLocation(("тольятти", "tolyatti"), -2133978, 51),
    _MarketplaceLocation(("иркутск", "irkutsk"), -1257154, 63),
    _MarketplaceLocation(("барнаул", "barnaul"), -1255457, 197),
    _MarketplaceLocation(("хабаровск", "khabarovsk"), -1273793, 76),
    _MarketplaceLocation(("владивосток", "vladivostok"), -1274204, 75),
    _MarketplaceLocation(("ярославль", "yaroslavl"), -2133855, 16),
    _MarketplaceLocation(("махачкала", "makhachkala"), -2144509, 28),
    _MarketplaceLocation(("томск", "tomsk"), -1255566, 67),
    _MarketplaceLocation(("оренбург", "orenburg"), -1261647, 48),
    _MarketplaceLocation(("кемерово", "kemerovo"), -1254838, 64),
    _MarketplaceLocation(("новокузнецк", "novokuznetsk"), -1254840, 64),
    _MarketplaceLocation(("рязань", "ryazan"), -2133856, 11),
    _MarketplaceLocation(("астрахань", "astrakhan"), -2144258, 37),
    _MarketplaceLocation(("набережные челны", "naberezhnye chelny"), -2133479, 43),
    _MarketplaceLocation(("пенза", "penza"), -2133916, 49),
    _MarketplaceLocation(("липецк", "lipetsk"), -2133858, 9),
    _MarketplaceLocation(("тула", "tula"), -2133857, 15),
    _MarketplaceLocation(("киров", "kirov"), -2133476, 46),
    _MarketplaceLocation(("чебоксары", "cheboksary"), -2133480, 45),
    _MarketplaceLocation(("улан-удэ", "ulan-ude"), -1268443, 198),
    _MarketplaceLocation(("калининград", "kaliningrad"), -2130032, 22),
    _MarketplaceLocation(("сочи", "sochi"), -2140649, 239),
    _MarketplaceLocation(("ставрополь", "stavropol"), -2133988, 36),
    _MarketplaceLocation(("белгород", "belgorod"), -2133911, 4),
    _MarketplaceLocation(("тверь", "tver"), -2133853, 14),
    _MarketplaceLocation(("иваново", "ivanovo"), -2133861, 5),
    _MarketplaceLocation(("брянск", "bryansk"), -2133906, 191),
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


_WB_DEST_MAP = _build_lookup("wb_dest")
_YM_REGION_MAP = _build_lookup("ym_region")

_WB_DEFAULT_DEST = _WB_DEST_MAP["москва"]
_YM_DEFAULT_REGION = _YM_REGION_MAP["москва"]


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
