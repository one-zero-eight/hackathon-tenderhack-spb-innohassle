import os
from pathlib import Path

from src.config_schema import ApiSettings, AuthSettings, OzonSettings, Settings, WildberriesSettings

settings_path = os.getenv("SETTINGS_PATH", "settings.yaml")
settings_path_obj = Path(settings_path)
settings: Settings = Settings.from_yaml(settings_path_obj)
api_settings: ApiSettings = settings.api_settings
auth_settings: AuthSettings = settings.auth_settings
ozon_settings: OzonSettings = settings.ozon_settings
wildberries_settings: WildberriesSettings = settings.wildberries_settings
settings_dir: Path | None = settings_path_obj.parent if settings_path_obj.is_file() else None
