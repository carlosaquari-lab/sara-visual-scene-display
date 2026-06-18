from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Sequence

from PIL import Image, ImageTk

from app import config
from app.i18n import tr


class SceneManagerPanel(ttk.Frame):
    """Left-panel scene navigation and management controls."""

    def __init__(
        self,
        master,
        on_previous: Callable[[], None],
        on_play_scene: Callable[[], None],
        on_next: Callable[[], None],
        on_scene_change: Callable[[int], None],
        on_add_scene: Callable[[], None],
        on_duplicate_scene: Callable[[], None],
        on_delete_scene: Callable[[], None],
        on_grid_change: Callable[[str], None],
        on_text_style: Callable[[], None],
        on_storyboard: Callable[[], None],
        on_modify_scene: Callable[[], None] | None = None,
        on_user_mode: Callable[[], None] | None = None,
    ):
        super().__init__(master, padding=(0, 4, 0, 0))
        self.columnconfigure(0, weight=1)
        self._callbacks = {
            "prev": on_previous,
            "play": on_play_scene,
            "next": on_next,
            "scene_change": on_scene_change,
            "add": on_add_scene,
            "duplicate": on_duplicate_scene,
            "delete": on_delete_scene,
            "grid_change": on_grid_change,
            "text_style": on_text_style,
            "storyboard": on_storyboard,
            "modify": on_modify_scene or (lambda: None),
            "user_mode": on_user_mode or (lambda: None),
        }

        self._style = ttk.Style(self)
        self._style.configure("SceneNav.TButton", font=("Arial", 10, "bold"))
        self._nav_button_photos: dict[str, ImageTk.PhotoImage] = {}

        nav = ttk.Frame(self)
        nav.grid(row=0, column=0, sticky="ew")
        nav.columnconfigure((0, 1, 2, 3), weight=1)
        self.prev_button = ttk.Button(nav, command=self._callbacks["prev"], style="SceneNav.TButton")
        self.prev_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.play_scene_button = ttk.Button(nav, command=self._callbacks["play"], style="SceneNav.TButton")
        self.play_scene_button.grid(row=0, column=1, sticky="ew", padx=6)
        self.settings_button = ttk.Button(nav, command=self._callbacks["modify"], style="SceneNav.TButton")
        self.settings_button.grid(row=0, column=2, sticky="ew", padx=6)
        self.next_button = ttk.Button(nav, command=self._callbacks["next"], style="SceneNav.TButton")
        self.next_button.grid(row=0, column=3, sticky="ew", padx=(6, 0))
        # 0.1.14: hide lower scene navigation icon row to gain vertical space.
        nav.grid_remove()

        self.current_scene_label = ttk.Label(self)
        self.current_scene_label.grid(row=1, column=0, sticky="w", pady=(4, 0))
        self.scene_selector_var = tk.StringVar()
        self.scene_selector = ttk.Combobox(self, textvariable=self.scene_selector_var, state="readonly")
        self.scene_selector.grid(row=2, column=0, sticky="ew", pady=(3, 5))
        self.scene_selector.bind("<<ComboboxSelected>>", self._emit_scene_change)

        self.design_frame = ttk.Frame(self)
        self.design_frame.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        for col in range(7):
            self.design_frame.columnconfigure(col, weight=0)
        self.design_frame.columnconfigure(7, weight=1)

        self.add_button = ttk.Button(self.design_frame, command=self._callbacks["add"], width=10)
        self.add_button.grid(row=0, column=0, sticky="w")
        self.duplicate_button = ttk.Button(self.design_frame, command=self._callbacks["duplicate"], width=10)
        self.duplicate_button.grid(row=0, column=1, sticky="w", padx=(6, 0))
        self.delete_button = ttk.Button(self.design_frame, command=self._callbacks["delete"], width=10)
        self.delete_button.grid(row=0, column=2, sticky="w", padx=(6, 12))

        self.cells_label = ttk.Label(self.design_frame)
        self.cells_label.grid(row=0, column=3, sticky="w")
        self.grid_selector_var = tk.StringVar()
        self.grid_selector = ttk.Combobox(self.design_frame, textvariable=self.grid_selector_var, state="readonly", values=config.GRID_PRESET_LABELS, width=6)
        self.grid_selector.grid(row=0, column=4, sticky="w", padx=(6, 0))
        self.grid_selector.bind("<<ComboboxSelected>>", self._emit_grid_change)

        self.text_style_button = ttk.Button(self.design_frame, command=self._callbacks["text_style"], width=12)
        self.text_style_button.grid(row=0, column=5, sticky="w", padx=(10, 0))
        self.storyboard_button = ttk.Button(self.design_frame, command=self._callbacks["storyboard"], width=8)
        self.storyboard_button.grid(row=0, column=6, sticky="w", padx=(10, 0))

        self.hint_label = ttk.Label(self, foreground="#666666")
        self._apply_nav_icons()
        self.apply_language()

    def _load_icon(self, icon_name: str, size: int = 28):
        path = config.ASSETS_ICONS_DIR / f"{icon_name}.png"
        if not path.exists():
            return None
        try:
            image = Image.open(path).convert("RGBA")
            image.thumbnail((size, size), Image.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self._nav_button_photos[icon_name] = photo
            return photo
        except Exception:
            return None

    def _apply_nav_icons(self):
        mapping = [
            (self.prev_button, "scene_previous", tr("nav_previous")),
            (self.play_scene_button, "altavoz_scene", tr("nav_scene_audio")),
            (self.settings_button, "wrench_clear", "Ajustes"),
            (self.next_button, "scene_next", tr("nav_next")),
        ]
        for button, icon_name, fallback_text in mapping:
            photo = self._load_icon(icon_name)
            if photo is not None:
                button.configure(image=photo, text="")
            else:
                button.configure(text=fallback_text)

    def apply_language(self) -> None:
        self._apply_nav_icons()
        self.current_scene_label.configure(text=tr("current_scene"))
        self.add_button.configure(text=tr("btn_add_short"))
        self.duplicate_button.configure(text=tr("btn_duplicate"))
        self.delete_button.configure(text=tr("btn_delete"))
        self.cells_label.configure(text=tr("cells_per_scene"))
        self.text_style_button.configure(text=tr("text_cells"))
        self.storyboard_button.configure(text=tr("panel_button"))
        self.hint_label.configure(text="")

    def _emit_scene_change(self, _event=None) -> None:
        idx = self.scene_selector.current()
        if idx >= 0:
            self._callbacks["scene_change"](idx)

    def _emit_grid_change(self, _event=None) -> None:
        self._callbacks["grid_change"](self.grid_selector_var.get())

    def set_scene_values(self, values: Sequence[str], current_index: int) -> None:
        self.scene_selector.configure(values=list(values))
        if values and current_index >= 0:
            self.scene_selector.current(current_index)

    def set_grid_value(self, label: str) -> None:
        self.grid_selector_var.set(label)

    def set_visible(self, visible: bool) -> None:
        # Sara 0.1.15: the lower scene selector/options panel is intentionally hidden.
        self.grid_remove()

    def set_design_mode(self, is_design: bool) -> None:
        if is_design:
            self.design_frame.grid()
        else:
            self.design_frame.grid_remove()
