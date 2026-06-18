from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from typing import Callable

from PIL import Image, ImageTk

from app.i18n import localize_scene_title, tr
from app.models import StoryProject

THUMB_SIZE = (220, 140)
MINI_CELL_SIZE = (30, 30)
SELECT_BORDER = '#c62828'
NORMAL_BORDER = '#c9c9c9'
SELECT_BG = '#fff0f0'
NORMAL_BG = '#f7f7f7'
TITLE_BG = '#ffffff'
CANVAS_BG = '#ececec'


class StoryboardDialog(tk.Toplevel):
    def __init__(self, master, project: StoryProject, current_index: int, on_go: Callable[[int], None], on_move: Callable[[int, int], None], on_rename: Callable[[int, str], None], on_delete: Callable[[int], None] | None = None):
        super().__init__(master)
        self.title(tr("scene_panel_title"))
        self.transient(master)
        self.grab_set()
        self.geometry('1120x680')
        self.minsize(900, 560)
        self.configure(bg=CANVAS_BG)
        self.project = project
        self.current_index = current_index
        self.selected_index = current_index
        self.on_go = on_go
        self.on_move = on_move
        self.on_rename = on_rename
        self.on_delete = on_delete
        self._photos = []
        self._entry_vars: list[tk.StringVar] = []

        outer = ttk.Frame(self, padding=12)
        outer.pack(fill='both', expand=True)
        ttk.Label(outer, text=tr("scene_panel_title"), font=('Arial', 13, 'bold')).pack(anchor='w')
        ttk.Label(outer, text=tr("scene_panel_subtitle"), foreground='#555555').pack(anchor='w', pady=(0, 8))

        toolbar = tk.Frame(outer, bg=TITLE_BG, highlightbackground='#d4d4d4', highlightthickness=1)
        toolbar.pack(fill='x', pady=(0, 10))
        left = tk.Frame(toolbar, bg=TITLE_BG)
        left.pack(side='left', padx=10, pady=8)
        self.selection_label = tk.Label(left, text='', bg=TITLE_BG, font=('Arial', 10, 'bold'))
        self.selection_label.pack(anchor='w')
        self.help_label = tk.Label(left, text=tr("scene_panel_help"), bg=TITLE_BG, fg='#555555')
        self.help_label.pack(anchor='w')

        right = tk.Frame(toolbar, bg=TITLE_BG)
        right.pack(side='right', padx=10, pady=8)
        self.move_left_btn = tk.Button(right, text='◀', font=('Arial', 26, 'bold'), width=3, command=lambda: self._move_selected(-1), bg=TITLE_BG, activebackground='#f3f3f3', activeforeground='black', relief='flat', bd=0, highlightthickness=0, cursor='hand2')
        self.move_left_btn.pack(side='left', padx=(0, 10), ipadx=4, ipady=0)
        self.go_btn = ttk.Button(right, text=tr("open_scene"), command=self._go_selected)
        self.go_btn.pack(side='left', padx=6, ipadx=10, ipady=6)
        self.move_right_btn = tk.Button(right, text='▶', font=('Arial', 26, 'bold'), width=3, command=lambda: self._move_selected(1), bg=TITLE_BG, activebackground='#f3f3f3', activeforeground='black', relief='flat', bd=0, highlightthickness=0, cursor='hand2')
        self.move_right_btn.pack(side='left', padx=(10, 8), ipadx=4, ipady=0)

        self.canvas = tk.Canvas(outer, highlightthickness=0, bg=CANVAS_BG)
        self.scroll = ttk.Scrollbar(outer, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.scroll.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)

        self.inner = tk.Frame(self.canvas, bg=CANVAS_BG)
        self._canvas_window = self.canvas.create_window((0, 0), window=self.inner, anchor='nw')
        self.inner.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        self.canvas.bind_all('<MouseWheel>', self._on_mousewheel, add='+')

        self.close_btn = ttk.Button(right, text=tr("close"), command=self._close)
        self.close_btn.pack(side='left', padx=(8, 0), ipadx=8, ipady=6)
        self._render()

    def _close(self):
        try:
            self.canvas.unbind_all('<MouseWheel>')
        except Exception:
            pass
        self.destroy()

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), 'units')

    def _on_canvas_configure(self, event):
        try:
            self.canvas.itemconfigure(self._canvas_window, width=event.width)
        except Exception:
            pass

    def _thumb_for_scene(self, scene):
        if scene.background_image and os.path.exists(scene.background_image):
            try:
                image = Image.open(scene.background_image).convert('RGBA')
                image.thumbnail(THUMB_SIZE, Image.LANCZOS)
                return ImageTk.PhotoImage(image)
            except Exception:
                return None
        return None

    def _mini_preview(self, cell):
        if getattr(cell, 'image_path', None) and os.path.exists(cell.image_path):
            try:
                image = Image.open(cell.image_path).convert('RGBA')
                image.thumbnail(MINI_CELL_SIZE, Image.LANCZOS)
                bg = Image.new('RGBA', MINI_CELL_SIZE, (255, 255, 255, 0))
                x = (MINI_CELL_SIZE[0] - image.size[0]) // 2
                y = (MINI_CELL_SIZE[1] - image.size[1]) // 2
                bg.paste(image, (x, y), image)
                return ImageTk.PhotoImage(bg)
            except Exception:
                return None
        return None

    def _select(self, index: int):
        self.selected_index = index
        self._render()

    def _go_selected(self):
        self.on_go(self.selected_index)
        self._close()

    def _move_selected(self, delta: int):
        target = max(0, min(self.selected_index + delta, len(self.project.scenes) - 1))
        if target == self.selected_index:
            return
        self.on_move(self.selected_index, target)
        self.selected_index = target
        self.current_index = target
        self._render()

    def _rename(self, index: int, value: str):
        self.on_rename(index, value)
        self._render()

    def _delete_selected(self):
        if self.on_delete is None or not self.project.scenes:
            return
        index = self.selected_index
        self.on_delete(index)
        if self.project.scenes:
            self.selected_index = max(0, min(index, len(self.project.scenes) - 1))
            self.current_index = self.selected_index
        self._render()

    def _bind_select_only(self, widget, index: int):
        widget.bind('<Button-1>', lambda e, i=index: self._select(i), add='+')
        widget.bind('<Double-Button-1>', lambda e, i=index: (self._select(i), self._go_selected()), add='+')

    def _bind_card_select(self, *widgets, index: int):
        for widget in widgets:
            self._bind_select_only(widget, index)

    def _render_cell_strip(self, parent, scene, bg: str):
        filled = [cell for cell in scene.cells if getattr(cell, 'text', '') or getattr(cell, 'image_path', '')]
        strip = tk.Frame(parent, bg=bg)
        strip.pack(fill='x', pady=(8, 0))
        shown = filled[:5]
        row = tk.Frame(strip, bg=bg)
        row.pack(anchor='w')
        if not shown:
            tk.Label(strip, text=tr("no_cells_configured"), anchor='w', fg='#666666', bg=bg).pack(anchor='w', pady=(4, 0))
            return
        for cell in shown:
            box = tk.Frame(row, width=36, height=36, bg='white', highlightbackground='#cfcfcf', highlightthickness=1)
            box.pack(side='left', padx=(0, 5))
            box.pack_propagate(False)
            photo = self._mini_preview(cell)
            self._photos.append(photo)
            if photo:
                tk.Label(box, image=photo, bg='white').pack(fill='both', expand=True)
            else:
                label = (getattr(cell, 'text', '') or '·')[:2].upper()
                tk.Label(box, text=label, bg='white', font=('Arial', 8, 'bold')).pack(fill='both', expand=True)
        if len(filled) > len(shown):
            tk.Label(row, text=f'+{len(filled)-len(shown)}', bg=bg, fg='#555555', font=('Arial', 9, 'bold')).pack(side='left', padx=(6, 0))

    def _update_toolbar_status(self):
        total = len(self.project.scenes)
        if total == 0:
            self.selection_label.configure(text=tr("no_scenes"))
            self.move_left_btn.configure(state='disabled')
            self.move_right_btn.configure(state='disabled')
            self.go_btn.configure(state='disabled')
            return
        scene = self.project.scenes[self.selected_index]
        title = localize_scene_title(scene.title, self.selected_index + 1)
        self.selection_label.configure(text=tr("selected_scene", current=self.selected_index + 1, total=total, title=title))
        self.move_left_btn.configure(state='normal' if self.selected_index > 0 else 'disabled')
        self.move_right_btn.configure(state='normal' if self.selected_index < total - 1 else 'disabled')
        self.go_btn.configure(state='normal')

    def _render(self):
        for child in self.inner.winfo_children():
            child.destroy()
        self._photos.clear()
        self._entry_vars.clear()
        total_scenes = len(self.project.scenes)
        if total_scenes <= 1:
            columns = 1
        elif total_scenes == 2:
            columns = 2
        else:
            columns = 3
        self._update_toolbar_status()

        available_width = max(860, self.canvas.winfo_width() or 0)
        card_width = max(260, (available_width - (columns + 1) * 20) // columns)

        for idx, scene in enumerate(self.project.scenes):
            selected = idx == self.selected_index
            bg = SELECT_BG if selected else NORMAL_BG
            border = SELECT_BORDER if selected else NORMAL_BORDER
            card = tk.Frame(self.inner, width=card_width, bg=bg, highlightbackground=border, highlightthickness=3 if selected else 1, bd=0)
            card.grid_propagate(False)
            r, c = divmod(idx, columns)
            card.grid(row=r, column=c, padx=10, pady=10, sticky='nw')
            card.configure(cursor='hand2')

            inner = tk.Frame(card, bg=bg, padx=10, pady=10)
            inner.pack(fill='both', expand=True)
            header = tk.Frame(inner, bg=bg)
            header.pack(fill='x')
            scene_badge = tk.Label(header, text=tr("scene_badge", index=idx + 1), font=('Arial', 10, 'bold'), bg=SELECT_BORDER if selected else '#646464', fg='white', padx=8, pady=3)
            scene_badge.pack(side='left')
            title_var = tk.StringVar(value=localize_scene_title(scene.title, idx + 1))
            self._entry_vars.append(title_var)
            entry = ttk.Entry(inner, textvariable=title_var, width=30)
            entry.pack(fill='x', pady=(8, 8))
            entry.bind('<FocusOut>', lambda e, i=idx, v=title_var: self._rename(i, v.get()))
            entry.bind('<Return>', lambda e, i=idx, v=title_var: self._rename(i, v.get()))

            photo = self._thumb_for_scene(scene)
            self._photos.append(photo)
            thumb_wrap = tk.Frame(inner, bg=bg)
            thumb_wrap.pack(fill='both', expand=True)
            thumb = tk.Label(thumb_wrap, image=photo, text='' if photo else tr("scene_no_image"), anchor='center', relief='sunken', bg='white')
            thumb.pack(fill='both', expand=True, ipadx=8, ipady=8)
            thumb_wrap.configure(height=THUMB_SIZE[1] + 16)
            thumb_wrap.pack_propagate(False)

            filled_count = len([cell for cell in scene.cells if getattr(cell, 'text', '') or getattr(cell, 'image_path', '')])
            self._render_cell_strip(inner, scene, bg)
            tk.Label(inner, text=tr("cells_with_content", count=filled_count), anchor='w', bg=bg, fg='#444444', font=('Arial', 9)).pack(anchor='w', pady=(8, 0))

            if self.on_delete is not None:
                delete_row = tk.Frame(inner, bg=bg)
                delete_row.pack(fill='x', pady=(10, 0))
                ttk.Button(delete_row, text=tr("delete_scene_button"), command=lambda i=idx: self._delete_card(i)).pack(anchor='center')

            self._bind_card_select(card, inner, header, scene_badge, thumb_wrap, thumb, index=idx)

        for col in range(columns):
            self.inner.columnconfigure(col, weight=0, minsize=card_width + 20)

    def _delete_card(self, index: int):
        self._select(index)
        self._delete_selected()
