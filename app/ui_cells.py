from __future__ import annotations

import os
import tkinter as tk
from typing import Callable, Optional

from PIL import Image, ImageTk

from app import config
from app.models import CellData
from app.services.fitzgerald_service import background_for_cell
from app.services.image_service import fitted_image_for_cell
from app.services.text_service import font_tuple, format_cell_text, normalize_style


class CellWidget(tk.Frame):
    def __init__(self, master, index: int, on_activate: Callable[[int], None], on_edit: Callable[[int], None], style_getter: Callable[[], dict] | None = None, mode_getter: Callable[[], str] | None = None, fit_mode_getter: Callable[[], str] | None = None):
        super().__init__(master, bd=1, relief=tk.RIDGE, bg="white", highlightthickness=1, highlightbackground="#B5B5B5")
        self.index = index
        self.on_activate = on_activate
        self.on_edit = on_edit
        self.style_getter = style_getter or (lambda: {})
        self.mode_getter = mode_getter or (lambda: "design")
        self.fit_mode_getter = fit_mode_getter or (lambda: getattr(config, "CELL_IMAGE_FIT_MODE", "contain"))
        self.cell: Optional[CellData] = None
        self._image_original: Optional[Image.Image] = None
        self._photo: Optional[ImageTk.PhotoImage] = None

        self.grid_propagate(False)
        self.image_label = tk.Label(self, bg="white", bd=0)
        self.text_label = tk.Label(self, bg="white", justify="center", fg=config.CELL_TEXT_COLOR)
        self.separator = tk.Frame(self, bg="#E1E1E1", height=1)

        self.rowconfigure(0, weight=88)
        self.rowconfigure(1, weight=0)
        self.rowconfigure(2, weight=12)
        self.columnconfigure(0, weight=1)

        self.image_label.grid(row=0, column=0, sticky="nsew", padx=2, pady=(2, 1))
        self.separator.grid(row=1, column=0, sticky="ew", padx=3)
        self.text_label.grid(row=2, column=0, sticky="nsew", padx=3, pady=(1, 3))

        for widget in (self, self.image_label, self.text_label, self.separator):
            widget.bind("<Button-1>", self._handle_activate)
            widget.bind("<Double-Button-1>", self._handle_edit)
            widget.bind("<Button-3>", self._handle_edit)

        self._render_after_id = None
        self.bind("<Configure>", lambda _e: self._on_resize())

    def _cancel_pending_render(self) -> None:
        if self._render_after_id is not None:
            try:
                self.after_cancel(self._render_after_id)
            except Exception:
                pass
            self._render_after_id = None

    def _clear_image_display(self) -> None:
        self._image_original = None
        self._photo = None
        try:
            self.image_label.configure(image="")
            self.image_label.image = None
        except Exception:
            pass

    def configure_cell(self, cell: CellData) -> None:
        # Cancel any delayed rendering from the previous cell/support before
        # binding this widget to new data. This avoids stale Tk PhotoImage
        # objects when a support image is replaced from the editor.
        self._cancel_pending_render()
        self.cell = cell
        self._clear_image_display()
        try:
            self.image_label.configure(text="")
        except Exception:
            pass
        bg = self._resolve_bg(cell)
        for widget in (self, self.image_label, self.text_label):
            widget.configure(bg=bg)

        if cell.image_path and os.path.exists(cell.image_path):
            try:
                self._image_original = Image.open(cell.image_path).convert("RGBA")
            except Exception:
                self._image_original = None
        else:
            self._image_original = None

        self._update_style()
        self._schedule_render()

    def configure_placeholder(self, title: str = "+", subtitle: str = "APOYO") -> None:
        """Render an editable empty support placeholder.

        This is used by SaraB's optional support strip so empty supports are
        visible in design mode without behaving like a communication grid.
        It must also clear any previously rendered image/text from the same
        widget so new/open project operations cannot leave stale support data
        on screen.
        """
        self._cancel_pending_render()
        self.cell = None
        self._clear_image_display()
        bg = "#FFFFFF"
        for widget in (self, self.image_label, self.text_label):
            widget.configure(bg=bg)
        # Hard-clear cached Tk image references and old labels before changing
        # layout. This prevents residual images/text after Nuevo proyecto or
        # Cargar proyecto.
        self.image_label.configure(text="")
        self.separator.grid_remove()
        self.image_label.grid_remove()
        self.text_label.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=6, pady=6)
        # SaraB support placeholders need a clear, easy-to-hit affordance.
        # The plus sign is intentionally larger than the text label.
        self.text_label.configure(
            text=f"{title}\n{subtitle}",
            font=("Arial", 18, "bold"),
            fg="#555555",
            justify="center",
            wraplength=max(self.winfo_width() - 12, 80),
        )
        self.configure(bg="#FFFFFF", highlightbackground="#B5B5B5", relief=tk.RIDGE)
        self.rowconfigure(0, weight=100)
        self.rowconfigure(2, weight=0)

    def clear_display(self) -> None:
        """Remove any cached image/text rendered in this widget."""
        self.cell = None
        self._cancel_pending_render()
        self._clear_image_display()
        self.image_label.configure(text="")
        self.text_label.configure(text="", image="")
        self.text_label.image = None
        self.separator.grid_remove()

    def _resolve_bg(self, cell: CellData) -> str:
        return background_for_cell(cell)

    def _current_style(self) -> dict:
        return normalize_style(self.style_getter() or {})

    def _update_style(self) -> None:
        style = self._current_style()
        text = format_cell_text(self.cell.text if self.cell else "", style)
        font = font_tuple(style, has_image=True)
        font_no_image = font_tuple(style, has_image=False)
        self.text_label.configure(text=text)

        has_image = bool(self.cell and self.cell.image_path and self._image_original is not None)
        if has_image:
            self.text_label.configure(font=font, fg=config.CELL_TEXT_COLOR)
            self.image_label.grid()
            if style["visible"] and text:
                self.separator.grid()
                self.text_label.grid(row=2, column=0, sticky="nsew", padx=3, pady=(1, 3))
            else:
                self.separator.grid_remove()
                self.text_label.grid_remove()
                self.rowconfigure(0, weight=100)
            self.rowconfigure(0, weight=88 if style["visible"] and text else 100)
            self.rowconfigure(2, weight=12 if style["visible"] and text else 0)
        else:
            self.image_label.grid_remove()
            self.separator.grid_remove()
            self.text_label.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=8, pady=8)
            self.text_label.configure(font=font_no_image, fg=config.CELL_TEXT_COLOR_NO_IMAGE)
            self.rowconfigure(0, weight=100)
            self.rowconfigure(2, weight=0)

    def _on_resize(self) -> None:
        wrap = max(self.winfo_width() - 10, 50)
        self.text_label.configure(wraplength=wrap)
        self._schedule_render()

    def _schedule_render(self) -> None:
        self._cancel_pending_render()
        self._render_after_id = self.after_idle(self._render_image)

    def _render_image(self) -> None:
        self._render_after_id = None
        if not self.cell or self._image_original is None:
            self._clear_image_display()
            try:
                self.image_label.configure(text="")
            except Exception:
                pass
            return

        # Use the actual allocated area after geometry has settled.
        width = self.image_label.winfo_width()
        height = self.image_label.winfo_height()
        if width <= 1 or height <= 1:
            width = max(self.winfo_width() - 10, 70)
            style = self._current_style()
            if style["visible"] and self.text_label.winfo_ismapped():
                height = max(int(self.winfo_height() * 0.82) - 8, 70)
            else:
                height = max(self.winfo_height() - 10, 70)

        src = self._image_original
        sw, sh = src.size
        if sw <= 0 or sh <= 0:
            return

        mode = self.mode_getter()
        image = fitted_image_for_cell(src, width, height, mode, self.fit_mode_getter())
        try:
            self._photo = ImageTk.PhotoImage(image, master=self.image_label)
            self.image_label.configure(image=self._photo)
            self.image_label.image = self._photo
        except tk.TclError:
            # Defensive fallback for rare cases where Tk invalidates an image
            # command during an editor refresh (e.g. replacing a support image).
            self._clear_image_display()
            try:
                self.image_label.configure(text="")
            except Exception:
                pass

    def _handle_activate(self, _event=None) -> None:
        self.on_activate(self.index)

    def _handle_edit(self, _event=None) -> None:
        self.on_edit(self.index)