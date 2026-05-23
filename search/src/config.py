from __future__ import annotations

import _bootstrap  # noqa: F401

import os
from pathlib import Path

from config_schema import Settings, YandexSearchSettings

_DEFAULT_SETTINGS = Path(__file__).resolve().parent.parent / "settings.yaml"
_settings_path = Path(os.getenv("SETTINGS_PATH", str(_DEFAULT_SETTINGS)))

if not _settings_path.is_file():
    msg = (
        f"Settings file not found: {_settings_path}. "
        "Copy settings.example.yaml to settings.yaml and configure yandex_search_settings."
    )
    raise FileNotFoundError(msg)

settings: Settings = Settings.from_yaml(_settings_path)
yandex_search_settings: YandexSearchSettings = settings.yandex_search_settings
