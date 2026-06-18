from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from app.i18n import tr
from app.ui_dialogs import _BaseDialog


class TextStyleDialog(_BaseDialog):
    """Dedicated dialog for global cell text style settings."""

    def __init__(self, master, size: int, bold: bool, uppercase: bool, visible: bool, on_save: Callable[[int, bool, bool, bool], None]):
        super().__init__(master, tr("cell_text_style"), 400, 240)
        self.on_save = on_save
        container = ttk.Frame(self, padding=12)
        container.grid(sticky="nsew")
        ttk.Label(container, text=tr("text_size")).grid(row=0, column=0, sticky="w")
        self.size_var = tk.IntVar(value=size)
        ttk.Spinbox(container, from_=8, to=16, textvariable=self.size_var, width=8).grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.bold_var = tk.BooleanVar(value=bold)
        ttk.Checkbutton(container, text=tr("bold"), variable=self.bold_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.upper_var = tk.BooleanVar(value=uppercase)
        ttk.Checkbutton(container, text=tr("show_uppercase"), variable=self.upper_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.visible_var = tk.BooleanVar(value=visible)
        ttk.Checkbutton(container, text=tr("show_text_below"), variable=self.visible_var).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        ttk.Label(container, text=tr("text_style_hint"), wraplength=340, foreground="#666666").grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))

        buttons = ttk.Frame(container)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(buttons, text=tr("cancel"), command=self.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(buttons, text=tr("apply"), command=self.apply).pack(side=tk.RIGHT)

    def apply(self) -> None:
        size = max(8, min(int(self.size_var.get()), 16))
        self.on_save(size, bool(self.bold_var.get()), bool(self.upper_var.get()), bool(self.visible_var.get()))
        self.destroy()
