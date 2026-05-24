"""Ozon delivery region via ``select_location`` query param (no address-book UI)."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

OZON_SELECT_LOCATION_PARAM = "select_location"

# City name / alias (lower) -> Ozon select_location UUID.
_OZON_SELECT_LOCATION_BY_KEY: dict[str, str] = {
    "москва": "0c5b2444-70a0-4932-980c-b4dc0d3f02b5",
    "moscow": "0c5b2444-70a0-4932-980c-b4dc0d3f02b5",
    "санкт-петербург": "c2deb16a-0330-4f05-821f-1d09c93331e6",
    "петербург": "c2deb16a-0330-4f05-821f-1d09c93331e6",
    "питер": "c2deb16a-0330-4f05-821f-1d09c93331e6",
    "saint petersburg": "c2deb16a-0330-4f05-821f-1d09c93331e6",
    "st. petersburg": "c2deb16a-0330-4f05-821f-1d09c93331e6",
    "новосибирск": "8dea00e3-9aab-4d8e-887c-ef2aaa546456",
    "novosibirsk": "8dea00e3-9aab-4d8e-887c-ef2aaa546456",
    "екатеринбург": "34f59155-b454-4169-a51c-1d582a65305c",
    "yekaterinburg": "34f59155-b454-4169-a51c-1d582a65305c",
    "ekaterinburg": "34f59155-b454-4169-a51c-1d582a65305c",
    "казань": "9715c3f9-62c2-4c3c-bda8-8aa72e7aef4b",
    "kazan": "9715c3f9-62c2-4c3c-bda8-8aa72e7aef4b",
    "иннополис": "9715c3f9-62c2-4c3c-bda8-8aa72e7aef4b",
    "innopolis": "9715c3f9-62c2-4c3c-bda8-8aa72e7aef4b",
    "нижний новгород": "1f66e37f-106e-4156-83c5-957f444beae7",
    "nizhny novgorod": "1f66e37f-106e-4156-83c5-957f444beae7",
}

DEFAULT_OZON_SELECT_LOCATION = _OZON_SELECT_LOCATION_BY_KEY["москва"]

RESOLVE_SELECT_LOCATION_JS = """
async (city) => {
  const uuidRe = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const pick = (value) => {
    if (typeof value === 'string' && uuidRe.test(value)) return value;
    if (Array.isArray(value)) {
      for (const item of value) {
        const found = pick(item);
        if (found) return found;
      }
      return null;
    }
    if (!value || typeof value !== 'object') return null;
    for (const key of ['uid', 'id', 'locationUid', 'selectLocation', 'fiasId', 'cityUid', 'value']) {
      const candidate = value[key];
      if (typeof candidate === 'string' && uuidRe.test(candidate)) return candidate;
    }
    for (const item of Object.values(value)) {
      const found = pick(item);
      if (found) return found;
    }
    return null;
  };
  const endpoints = [
    `/api/composer-api.bx/_action/v2/addressSuggest?query=${encodeURIComponent(city)}`,
    `/api/composer-api.bx/_action/v2/locationSuggest?query=${encodeURIComponent(city)}`,
    `/api/composer-api.bx/_action/v2/searchLocation?query=${encodeURIComponent(city)}`,
    `/api/composer-api.bx/_action/v2/suggest?query=${encodeURIComponent(city)}`,
  ];
  for (const url of endpoints) {
    try {
      const response = await fetch(url, {
        credentials: 'include',
        headers: { accept: 'application/json' },
      });
      if (!response.ok) continue;
      const data = await response.json();
      const id = pick(data);
      if (id) return id;
    } catch (e) {}
  }
  return null;
}
"""


def lookup_ozon_select_location_key(key: str | None) -> str | None:
    if key is None:
        return DEFAULT_OZON_SELECT_LOCATION
    normalized = key.strip().lower()
    if not normalized:
        return DEFAULT_OZON_SELECT_LOCATION
    return _OZON_SELECT_LOCATION_BY_KEY.get(normalized)


def append_select_location(path_or_url: str, select_location: str | None) -> str:
    if not select_location:
        return path_or_url
    parsed = urlparse(path_or_url)
    if parsed.scheme in ("http", "https"):
        query_pairs = [
            (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != OZON_SELECT_LOCATION_PARAM
        ]
        query_pairs.append((OZON_SELECT_LOCATION_PARAM, select_location))
        return urlunparse(parsed._replace(query=urlencode(query_pairs)))
    if "?" in path_or_url:
        base, query = path_or_url.split("?", 1)
        pairs = [(k, v) for k, v in parse_qsl(query, keep_blank_values=True) if k != OZON_SELECT_LOCATION_PARAM]
    else:
        base, pairs = path_or_url, []
    pairs.append((OZON_SELECT_LOCATION_PARAM, select_location))
    return f"{base}?{urlencode(pairs)}"
