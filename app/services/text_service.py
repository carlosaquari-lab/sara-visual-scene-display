from __future__ import annotations

from typing import Iterable

from app import config
from app.models import TextStyleConfig
from app.utils import clamp_text


def normalize_style(style: dict | TextStyleConfig | None) -> dict:
    if isinstance(style, TextStyleConfig):
        size = style.size
        bold = style.bold
        uppercase = style.uppercase
        visible = style.visible
    else:
        payload = dict(style or {})
        size = int(payload.get("size", config.CELL_TEXT_SIZE_DEFAULT))
        bold = bool(payload.get("bold", config.CELL_TEXT_BOLD_DEFAULT))
        uppercase = bool(payload.get("uppercase", config.CELL_TEXT_UPPERCASE_DEFAULT))
        visible = bool(payload.get("visible", config.CELL_TEXT_VISIBLE_DEFAULT))
    size = max(8, min(int(size), 16))
    return {"size": size, "bold": bool(bold), "uppercase": bool(uppercase), "visible": bool(visible)}


def visible_text(value: str | None, uppercase: bool = True) -> str:
    text = clamp_text(value).strip()
    return text.upper() if uppercase else text


def format_cell_text(text: str | None, style: dict | TextStyleConfig | None) -> str:
    normalized = normalize_style(style)
    return visible_text(text, uppercase=normalized["uppercase"])


def font_tuple(style: dict | TextStyleConfig | None, has_image: bool = True) -> tuple:
    normalized = normalize_style(style)
    size = normalized["size"] if has_image else min(normalized["size"] + 1, 16)
    return ("Arial", size, "bold" if normalized["bold"] else "normal")


def append_token(current_text: str, token: str) -> str:
    token = clamp_text(token).strip()
    if not token:
        return clamp_text(current_text)
    current = clamp_text(current_text).strip()
    return token if not current else f"{current} {token}"


def remove_last_token(current_text: str) -> str:
    parts = clamp_text(current_text).strip().split()
    return " ".join(parts[:-1]) if parts else ""


def clear_text() -> str:
    return ""


def automatic_size_for_grid(rows: int, cols: int) -> int:
    mapping = {(2, 2): 14, (2, 3): 13, (3, 3): 12, (3, 4): 10, (4, 5): 9}
    return mapping.get((rows, cols), config.CELL_TEXT_SIZE_DEFAULT)
