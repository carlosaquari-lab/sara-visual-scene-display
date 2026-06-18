from __future__ import annotations

import json
from pathlib import Path

from app import config


class SettingsService:
    """Small persistence layer for lightweight app preferences.

    For now we only persist the UI language, but keeping this logic separate
    makes the ongoing architecture cleanup clearer and avoids hardcoding file
    I/O inside the main UI class.
    """

    DEFAULTS = {
        "ui_language": config.DEFAULT_UI_LANGUAGE,
    }

    @classmethod
    def load(cls) -> dict:
        path = Path(config.SETTINGS_PATH)
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    merged = dict(cls.DEFAULTS)
                    merged.update(data)
                    return merged
        except Exception:
            pass
        return dict(cls.DEFAULTS)

    @classmethod
    def save(cls, settings: dict) -> None:
        path = Path(config.SETTINGS_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(cls.DEFAULTS)
        if isinstance(settings, dict):
            payload.update(settings)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def get_ui_language(cls) -> str:
        settings = cls.load()
        lang = settings.get("ui_language", config.DEFAULT_UI_LANGUAGE)
        return "en" if lang == "en" else "es"

    @classmethod
    def set_ui_language(cls, lang: str) -> None:
        settings = cls.load()
        settings["ui_language"] = "en" if lang == "en" else "es"
        cls.save(settings)
