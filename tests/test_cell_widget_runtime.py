import sys
import tkinter as tk
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import CellData
from app.ui_cells import CellWidget


@pytest.fixture
def hidden_root():
    root = tk.Tk()
    root.withdraw()
    try:
        yield root
    finally:
        try:
            root.update_idletasks()
        except tk.TclError:
            pass
        root.destroy()


def _png(path: Path, color: tuple[int, int, int]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (24, 24), color).save(path, format="PNG")
    return str(path)


def _cell(text: str, image_path: str = "", audio_path: str = "") -> CellData:
    return CellData(
        id=f"cell_{text or 'empty'}",
        position=0,
        text=text,
        image_path=image_path,
        audio_path=audio_path,
        tts_enabled=True,
        cell_type="visual_support",
        visible=True,
    )


def _widget(root) -> CellWidget:
    widget = CellWidget(
        root,
        0,
        on_activate=lambda _idx: None,
        on_edit=lambda _idx: None,
        style_getter=lambda: {"size": 9, "bold": True, "uppercase": True, "visible": True},
        mode_getter=lambda: "design",
        fit_mode_getter=lambda: "cover",
    )
    widget.configure(width=120, height=100)
    widget.pack()
    return widget


def test_cell_widget_replaces_support_image_without_stale_photoimage(hidden_root, tmp_path):
    widget = _widget(hidden_root)
    image_a = _png(tmp_path / "a.png", (255, 0, 0))
    image_b = _png(tmp_path / "b.png", (0, 0, 255))

    widget.configure_cell(_cell("first", image_path=image_a))
    hidden_root.update_idletasks()
    photo_a = widget._photo

    widget.configure_cell(_cell("second", image_path=image_b))
    hidden_root.update_idletasks()

    assert widget.cell.image_path == image_b
    assert widget._photo is not None
    assert widget._photo is not photo_a
    assert widget.image_label.image is widget._photo


def test_cell_widget_clear_display_removes_image_text_cell_and_pending_render(hidden_root, tmp_path):
    widget = _widget(hidden_root)
    image_path = _png(tmp_path / "support.png", (0, 255, 0))

    widget.configure_cell(_cell("clear me", image_path=image_path))
    widget.clear_display()

    assert widget.cell is None
    assert widget._image_original is None
    assert widget._photo is None
    assert widget._render_after_id is None
    assert widget.image_label.image is None
    assert widget.text_label.cget("text") == ""


def test_cell_widget_configure_placeholder_clears_previous_content(hidden_root, tmp_path):
    widget = _widget(hidden_root)
    image_path = _png(tmp_path / "support.png", (255, 255, 0))

    widget.configure_cell(_cell("old support", image_path=image_path))
    hidden_root.update_idletasks()