from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .constants import DEFAULT_START_DATE, INVIMA_URL


def user_data_dir() -> Path:
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    else:
        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        base = Path(xdg_data_home) if xdg_data_home else Path.home() / ".local" / "share"
    return base / "SIGAVI"


def resource_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


@dataclass(slots=True)
class Settings:
    template_path: str = ""
    data_dir: str = ""
    start_date: str = DEFAULT_START_DATE
    listing_url: str = INVIMA_URL
    max_pages: int = 500
    timeout_seconds: int = 35

    @property
    def database_path(self) -> Path:
        return Path(self.data_dir) / "BaseDatos" / "sigavi.db"

    @property
    def evidence_dir(self) -> Path:
        return Path(self.data_dir) / "Evidencia"

    @property
    def matrix_output_path(self) -> Path:
        return Path(self.data_dir) / "Matriz_Alertas_INVIMA_ACTUALIZADA.xlsx"

    @property
    def log_path(self) -> Path:
        return Path(self.data_dir) / "logs" / "sigavi.log"


def default_settings() -> Settings:
    data_dir = user_data_dir()
    template_name = "2026 - Propuesta Formato de Control y Seguimiento de Alertas Sanitarias SIGAVI.xlsx"
    bundled_template = resource_dir() / template_name
    if getattr(sys, "frozen", False) and bundled_template.is_file():
        persistent_template = data_dir / "Plantilla" / template_name
        if not persistent_template.exists():
            persistent_template.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bundled_template, persistent_template)
        preferred_template = persistent_template
    else:
        preferred_template = bundled_template
    return Settings(template_path=str(preferred_template) if preferred_template.is_file() else "", data_dir=str(data_dir))


def settings_path() -> Path:
    return user_data_dir() / "config.json"


def load_settings() -> Settings:
    path = settings_path()
    defaults = default_settings()
    if not path.exists():
        return defaults
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fields = Settings.__dataclass_fields__
        safe = {key: value for key, value in payload.items() if key in fields}
        loaded = Settings(**{**asdict(defaults), **safe})
        if not Path(loaded.template_path).is_file() and defaults.template_path:
            loaded.template_path = defaults.template_path
        return loaded
    except (OSError, ValueError, TypeError):
        return defaults


def save_settings(settings: Settings) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
