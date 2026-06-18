import json
import os
import tkinter as tk
from typing import Iterable


def ensure_dirs(*paths: Iterable[str]) -> None:
    for path in paths:
        os.makedirs(path, exist_ok=True)


def load_json(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def save_json(path: str, payload) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)


def maximize_window(root: tk.Tk) -> None:
    try:
        root.state("zoomed")
        return
    except Exception:
        pass
    try:
        root.attributes("-zoomed", True)
        return
    except Exception:
        pass
    try:
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.geometry(f"{width}x{height}+0+0")
    except Exception:
        root.geometry("1280x900")


def clamp_text(value: str | None) -> str:
    return "" if value is None else str(value)


def visible_text(value: str | None, uppercase: bool = True) -> str:
    text = clamp_text(value).strip()
    return text.upper() if uppercase else text


def uppercase_visible_text(value: str | None) -> str:
    return visible_text(value, uppercase=True)
