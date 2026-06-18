from __future__ import annotations

from pathlib import Path
import os
import tkinter as tk
from tkinter import colorchooser, filedialog, ttk
from urllib.error import HTTPError, URLError
from typing import Callable

from PIL import Image, ImageTk

from app import config
from app.i18n import default_scene_title, get_language, tr, typology_options
from app.models import CellData, HotspotData, Scene
from app.vocabulary_categories import get_vocabulary_category, get_vocabulary_category_columns, vocabulary_translation_key
from app.services.arasaac_service import ArasaacResult, ArasaacService, ArasaacServiceError
from app.services.dialog_service import DialogService
from app.services.fitzgerald_service import apply_typology_to_cell, category_for_typology
from app.services.text_service import visible_text


class _BaseDialog(tk.Toplevel):
    def __init__(self, master, title: str, width: int, height: int):
        super().__init__(master)
        self.title(title)
        self.transient(master)
        self.grab_set()
        self.attributes("-topmost", True)
        self.resizable(False, False)
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(width, max(screen_w - 120, 420))
        height = min(height, max(screen_h - 120, 320))
        x = max(20, min(master.winfo_rootx() + 50, screen_w - width - 40))
        y = max(20, min(master.winfo_rooty() + 30, screen_h - height - 60))
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.focus_force()
        self.dialogs = DialogService()

    def _browse_open(self, **kwargs):
        self.attributes("-topmost", False)
        try:
            return filedialog.askopenfilename(parent=self, **kwargs)
        finally:
            self.attributes("-topmost", True)
            self.lift()
            self.focus_force()

    def _set_dialog_geometry(self, width: int, height: int) -> None:
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(width, max(screen_w - 120, 420))
        height = min(height, max(screen_h - 120, 320))
        x = max(20, min(self.master.winfo_rootx() + 50, screen_w - width - 40))
        y = max(20, min(self.master.winfo_rooty() + 30, screen_h - height - 60))
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _set_dialog_right_of_master(self, width: int, height: int, gap: int = 18) -> None:
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(width, max(screen_w - 120, 420))
        height = min(height, max(screen_h - 120, 320))
        desired_x = self.master.winfo_rootx() + self.master.winfo_width() + gap
        x = min(desired_x, screen_w - width - 20)
        if x < 20:
            x = max(20, min(self.master.winfo_rootx() + 50, screen_w - width - 40))
        y = max(20, min(self.master.winfo_rooty() + 30, screen_h - height - 60))
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _set_dialog_right_of_widget(self, widget, width: int, height: int, gap: int = 16) -> None:
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(width, max(screen_w - 120, 420))
        height = min(height, max(screen_h - 120, 320))
        try:
            widget.update_idletasks()
            desired_x = widget.winfo_rootx() + widget.winfo_width() + gap
            desired_y = widget.winfo_rooty()
        except Exception:
            self._set_dialog_right_of_master(width, height, gap=gap)
            return
        x = min(desired_x, screen_w - width - 20)
        if x < 20:
            x = max(20, min(self.master.winfo_rootx() + 50, screen_w - width - 40))
        y = max(20, min(desired_y, screen_h - height - 40))
        self.geometry(f"{width}x{height}+{x}+{y}")


class ArasaacSearchDialog(_BaseDialog):
    def __init__(self, master, initial_query: str = "", on_select: Callable[[str], None] | None = None):
        super().__init__(master, tr("arasaac_dialog_title"), 920, 560)
        self.on_select = on_select
        self.service = ArasaacService()
        self.result_photos: list[ImageTk.PhotoImage] = []
        self.results: list[ArasaacResult] = []
        self._result_selected = False

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        outer = ttk.Frame(self, padding=12)
        outer.grid(sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        top = ttk.Frame(outer)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text=tr("arasaac_search_label")).grid(row=0, column=0, sticky="w")
        self.query_var = tk.StringVar(value=initial_query)
        entry = ttk.Entry(top, textvariable=self.query_var, width=36)
        entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        entry.bind("<Return>", lambda _e: self.perform_search())

        ttk.Label(top, text=tr("arasaac_language_label")).grid(row=0, column=2, sticky="w")
        default_lang = 'en' if get_language() == 'en' else 'es'
        self.lang_var = tk.StringVar(value=default_lang)
        ttk.Combobox(top, textvariable=self.lang_var, values=["es", "en"], state="readonly", width=8).grid(row=0, column=3, sticky="w", padx=(8, 8))
        ttk.Button(top, text=tr("arasaac_search_button"), command=self.perform_search).grid(row=0, column=4, sticky="e")

        self.status_var = tk.StringVar(value=tr("arasaac_status_idle"))
        ttk.Label(outer, textvariable=self.status_var, foreground="#555555").grid(row=1, column=0, sticky="w", pady=(8, 8))

        results_holder = ttk.Frame(outer)
        results_holder.grid(row=2, column=0, sticky="nsew")
        results_holder.columnconfigure(0, weight=1)
        results_holder.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(results_holder, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(results_holder, orient="vertical", command=self.canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.results_frame = ttk.Frame(self.canvas)
        self.window_id = self.canvas.create_window((0, 0), window=self.results_frame, anchor="nw")
        self.results_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window_id, width=e.width))
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel, add="+")

        button_bar = ttk.Frame(outer)
        button_bar.grid(row=3, column=0, sticky="e", pady=(10, 0))
        ttk.Button(button_bar, text=tr("close"), command=self._safe_destroy).pack(side=tk.RIGHT)

        self.bind("<Escape>", lambda _e: self._safe_destroy())
        self.protocol("WM_DELETE_WINDOW", self._safe_destroy)
        self.after(80, entry.focus_set)
        if initial_query.strip():
            self.after(120, self.perform_search)

    def _bind_result_card(self, widget, result: ArasaacResult) -> None:
        if isinstance(widget, ttk.Button):
            return
        widget.bind("<Button-1>", lambda _e, r=result: self._use_result(r))
        widget.bind("<Double-1>", lambda _e, r=result: self._use_result(r))

    def _bind_descendants(self, widget, result: ArasaacResult) -> None:
        self._bind_result_card(widget, result)
        for child in widget.winfo_children():
            self._bind_descendants(child, result)

    def _safe_destroy(self):
        try:
            self.canvas.unbind_all("<MouseWheel>")
        except Exception:
            pass
        self.destroy()

    def _on_mousewheel(self, event):
        if self.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def perform_search(self) -> None:
        query = self.query_var.get().strip()
        if not query:
            self.status_var.set(tr("arasaac_enter_search"))
            return
        self.status_var.set(tr("arasaac_status_searching"))
        self.update_idletasks()
        try:
            self.results = self.service.search_pictograms(query, self.lang_var.get().strip() or 'es')
        except ArasaacServiceError as e:
            self.status_var.set(tr("arasaac_status_error"))
            if e.kind in {'network', 'http'}:
                base_msg = tr("arasaac_error_network")
            else:
                base_msg = tr("arasaac_error_generic")
            self.dialogs.error(tr("arasaac_dialog_title"), base_msg + "\n\n" + str(e), parent=self)
            return
        except Exception as e:
            self.status_var.set(tr("arasaac_status_error"))
            self.dialogs.error(tr("arasaac_dialog_title"), tr("arasaac_error_generic") + "\n\n" + str(e), parent=self)
            return
        self._render_results()

    def _render_results(self) -> None:
        for child in self.results_frame.winfo_children():
            child.destroy()
        self.result_photos.clear()
        if not self.results:
            self.status_var.set(tr("arasaac_status_no_results"))
            ttk.Label(self.results_frame, text=tr("arasaac_status_no_results")).grid(row=0, column=0, sticky="w", padx=6, pady=6)
            return
        columns = 5
        shown = self.results[:15]
        for idx, result in enumerate(shown):
            row, col = divmod(idx, columns)
            card = ttk.Frame(self.results_frame, padding=8, relief=tk.RIDGE)
            card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
            card.columnconfigure(0, weight=1)
            try:
                thumb = self.service.fetch_thumbnail_image(result)
                photo = ImageTk.PhotoImage(thumb)
                self.result_photos.append(photo)
                lbl = ttk.Label(card, image=photo, anchor='center')
                lbl.grid(row=0, column=0, pady=(0, 6))
            except Exception:
                lbl = ttk.Label(card, text=str(result.pictogram_id), anchor='center')
                lbl.grid(row=0, column=0, pady=(0, 6))
            label_text = result.label if len(result.label) <= 20 else result.label[:17] + '...'
            text_lbl = ttk.Label(card, text=label_text, anchor='center')
            text_lbl.grid(row=1, column=0, sticky='ew')
            btn = ttk.Button(card, text=tr("arasaac_use_button"), command=lambda r=result: self._use_result(r))
            btn.grid(row=2, column=0, pady=(6, 0), sticky='ew')
            self._bind_descendants(card, result)
        self.status_var.set(tr("arasaac_status_results", count=len(self.results)))
        self.update_idletasks()
        self.canvas.yview_moveto(0)

    def _use_result(self, result: ArasaacResult) -> None:
        if self._result_selected or not self.winfo_exists():
            return
        self._result_selected = True
        try:
            local_path = self.service.download_pictogram(result)
            if self.on_select:
                self.on_select(local_path)
            self._safe_destroy()
        except ArasaacServiceError as e:
            self._result_selected = False
            if e.kind in {'network', 'http'}:
                base_msg = tr("arasaac_error_download")
            else:
                base_msg = tr("arasaac_error_generic")
            self.dialogs.error(tr("arasaac_dialog_title"), base_msg + "\n\n" + str(e), parent=self)
            return
        except Exception as e:
            self._result_selected = False
            self.dialogs.error(tr("arasaac_dialog_title"), tr("arasaac_error_generic") + "\n\n" + str(e), parent=self)
            return


class CellEditorDialog(_BaseDialog):
    def __init__(self, master, cell: CellData, on_save: Callable[[CellData], None], scene_id: str = "", project_path: str = ""):
        super().__init__(master, tr("dialog_edit_cell"), 780, 740)
        self.cell = CellData.from_dict(cell.to_dict())
        self.on_save = on_save
        self.scene_id = scene_id
        self.project_path = project_path
        self.preview_photo = None

        self._set_dialog_geometry(780, min(self.winfo_screenheight() - 80, 640))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        outer = ttk.Frame(self, padding=10)
        outer.grid(sticky="nsew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(outer, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=self.canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        container = ttk.Frame(self.canvas, padding=(2, 2, 6, 2))
        self.window_id = self.canvas.create_window((0, 0), window=container, anchor="nw")
        container.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window_id, width=e.width))

        help_text = tr("cell_editor_help")
        ttk.Label(container, text=help_text, wraplength=700, foreground="#555555").grid(row=0, column=0, sticky="ew", pady=(0, 8))

        body = ttk.Frame(container, padding=10)
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)

        ttk.Label(body, text=tr("cell_text")).grid(row=0, column=0, sticky="w")
        self.text_var = tk.StringVar(value=self.cell.text)
        self.text_entry = ttk.Entry(body, textvariable=self.text_var, width=52)
        self.text_entry.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(body, text=tr("image")).grid(row=2, column=0, sticky="w")
        image_buttons = ttk.Frame(body)
        image_buttons.grid(row=3, column=0, sticky="w", pady=(0, 6))
        ttk.Button(image_buttons, text=tr("select_image"), command=self.choose_image).pack(side=tk.LEFT)
        ttk.Button(image_buttons, text=tr("remove_image"), command=self.clear_image).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(image_buttons, text=tr("arasaac_open_button"), command=self.open_arasaac_search).pack(side=tk.LEFT, padx=(6, 0))
        media_row = ttk.Frame(body)
        media_row.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        media_row.columnconfigure(0, weight=3)
        media_row.columnconfigure(1, weight=2)

        preview_frame = ttk.Frame(media_row)
        preview_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        ttk.Label(preview_frame, text=tr("preview")).grid(row=0, column=0, sticky="w")
        self.preview = ttk.Label(preview_frame, relief=tk.SUNKEN, anchor="center")
        self.preview.grid(row=1, column=0, sticky="ew", pady=(0, 0), ipadx=4, ipady=4)

        sound_frame = ttk.LabelFrame(media_row, text=tr("sound"), padding=8)
        sound_frame.grid(row=0, column=1, sticky="nsew")
        self.tts_var = tk.BooleanVar(value=self.cell.tts_enabled)
        ttk.Checkbutton(sound_frame, text=tr("auto_tts"), variable=self.tts_var).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Button(sound_frame, text=tr("select_audio"), command=self.choose_audio).grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Button(sound_frame, text=tr("record_audio_button"), command=self.record_audio).grid(row=1, column=1, sticky="w", padx=(6, 0), pady=(6, 0))
        self.audio_preview_button = ttk.Button(sound_frame, text=tr("play_preview_button"), command=self.play_audio_preview)
        self.audio_preview_button.grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Button(sound_frame, text=tr("remove_audio"), command=self.clear_audio).grid(row=2, column=1, sticky="w", padx=(6, 0), pady=(6, 0))
        self.audio_label = ttk.Label(sound_frame, text=Path(self.cell.audio_path).name if self.cell.audio_path else tr("no_audio"), wraplength=220)
        self.audio_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self._refresh_audio_preview_button()

        sep = ttk.Separator(body, orient="horizontal")
        sep.grid(row=5, column=0, sticky="ew", pady=8)
        ttk.Label(body, text=tr("research"), font=("Arial", 10, "bold")).grid(row=6, column=0, sticky="w", pady=(0, 6))

        self.typology_pairs = typology_options()
        self.typology_label_by_id = {k: v for k, v in self.typology_pairs}
        self.typology_id_by_label = {v: k for k, v in self.typology_pairs}
        typology_default = self.typology_label_by_id.get(self.cell.key_typology or "none", self.typology_pairs[0][1])
        self.typology_var = tk.StringVar(value=typology_default)
        ttk.Label(body, text=tr("typology")).grid(row=7, column=0, sticky="w")
        self.typology_combo = ttk.Combobox(body, textvariable=self.typology_var, values=[v for _, v in self.typology_pairs], state="readonly", width=52)
        self.typology_combo.grid(row=8, column=0, sticky="ew", pady=(0, 8))
        self.typology_combo.bind("<<ComboboxSelected>>", lambda _e: self._sync_fitzgerald_from_typology())

        fitz_frame = ttk.LabelFrame(body, text=tr("fitzgerald_key"), padding=8)
        fitz_frame.grid(row=9, column=0, sticky="ew", pady=(0, 8))
        self.fitz_var = tk.BooleanVar(value=self.cell.fitzgerald_enabled)
        ttk.Checkbutton(fitz_frame, text=tr("fitz_auto"), variable=self.fitz_var, command=self._sync_fitzgerald_from_typology).grid(row=0, column=0, sticky="w")
        ttk.Label(fitz_frame, text=tr("applied_color")).grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.fitz_summary_var = tk.StringVar()
        ttk.Label(fitz_frame, textvariable=self.fitz_summary_var).grid(row=2, column=0, sticky="w")

        button_frame = ttk.Frame(container)
        button_frame.grid(row=2, column=0, sticky="e", pady=(8, 0))
        ttk.Button(button_frame, text=tr("cancel"), command=self._safe_destroy).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(button_frame, text=tr("apply"), command=self.apply).pack(side=tk.RIGHT)

        container.columnconfigure(0, weight=1)
        self.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
        self.protocol("WM_DELETE_WINDOW", self._safe_destroy)
        self._sync_fitzgerald_from_typology()
        self._update_preview()
        self.after(80, self._focus_text_entry)

    def _focus_text_entry(self) -> None:
        try:
            self.text_entry.focus_set()
            self.text_entry.icursor("end")
            if self.text_var.get().strip():
                self.text_entry.selection_range(0, "end")
        except Exception:
            pass

    def _bind_descendants(self, widget, result: ArasaacResult) -> None:
        self._bind_result_card(widget, result)
        for child in widget.winfo_children():
            self._bind_descendants(child, result)

    def _safe_destroy(self):
        try:
            self.unbind_all("<MouseWheel>")
        except Exception:
            pass
        self.destroy()

    def _on_mousewheel(self, event):
        if self.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def choose_image(self) -> None:
        path = self._browse_open(filetypes=config.SUPPORTED_IMAGE_TYPES)
        if path:
            path_obj = Path(path)
            self.cell.image_path = str(path_obj)
            self.cell.visual_source = 'local_image'
            self._update_preview()

    def clear_image(self) -> None:
        self.cell.image_path = ""
        self.cell.visual_source = 'none'
        self._update_preview()

    def open_arasaac_search(self) -> None:
        ArasaacSearchDialog(self, initial_query=self.text_var.get().strip(), on_select=self._apply_arasaac_image)

    def _apply_arasaac_image(self, path: str) -> None:
        if path:
            path_obj = Path(path)
            self.cell.image_path = str(path_obj)
            self.cell.visual_source = 'arasaac'
            self._update_preview()

    def choose_label_bg(self) -> None:
        color = colorchooser.askcolor(color=self.label_bg_var.get(), parent=self, title=tr("hotspot_label_bg_dialog"))[1]
        if color:
            self.label_bg_var.set(color)
            self.label_bg_preview.configure(bg=color)

    def choose_label_fg(self) -> None:
        color = colorchooser.askcolor(color=self.label_fg_var.get(), parent=self, title=tr("hotspot_label_fg_dialog"))[1]
        if color:
            self.label_fg_var.set(color)
            self.label_fg_preview.configure(bg=color, fg="white" if color.lower() == "#000000" else "black")

    def choose_audio(self) -> None:
        path = self._browse_open(filetypes=config.SUPPORTED_AUDIO_TYPES)
        if path:
            path_obj = Path(path)
            self.cell.audio_path = str(path_obj)
            self.audio_label.configure(text=path_obj.name)
            self._refresh_audio_preview_button()

    def clear_audio(self) -> None:
        self.cell.audio_path = ""
        self.audio_label.configure(text=tr("no_audio"))
        self._refresh_audio_preview_button()

    def _recording_path_for_cell(self) -> Path:
        from app.services.audio_recording_service import recording_path_for_hotspot
        cell_id = getattr(self.cell, "id", "") or f"cell_{getattr(self.cell, 'position', 0)}"
        return recording_path_for_hotspot(self.scene_id, cell_id, self.project_path)

    def _apply_recorded_audio(self, path: str | Path) -> None:
        path_obj = Path(path)
        self.cell.audio_path = str(path_obj)
        self.audio_label.configure(text=path_obj.name)
        self._refresh_audio_preview_button()

    def _refresh_audio_preview_button(self) -> None:
        try:
            has_audio = bool(str(getattr(self.cell, "audio_path", "") or "").strip())
            self.audio_preview_button.configure(state="normal" if has_audio else "disabled")
        except Exception:
            pass

    def _play_audio_file(self, path: str | Path) -> bool:
        from app.audio import AudioManager
        audio = AudioManager()
        return bool(audio.play_file(str(path)))

    def play_audio_preview(self) -> None:
        path = Path(getattr(self.cell, "audio_path", "") or "")
        if not path.exists():
            self.dialogs.warning(tr("play_preview_unavailable"), tr("play_preview_missing"), parent=self)
            return
        if not self._play_audio_file(path):
            self.dialogs.error(tr("play_preview_unavailable"), tr("play_preview_failed"), parent=self)

    def record_audio(self) -> None:
        RecordHotspotAudioDialog(self, destination_factory=self._recording_path_for_cell, on_recorded=self._apply_recorded_audio)

    def _update_preview(self) -> None:
        if self.cell.image_path and Path(self.cell.image_path).exists():
            try:
                image = Image.open(self.cell.image_path).convert("RGBA")
                image.thumbnail((150, 110), Image.LANCZOS)
                self.preview_photo = ImageTk.PhotoImage(image, master=self.preview)
                self.preview.configure(image=self.preview_photo, text="")
                self.preview.image = self.preview_photo
                return
            except Exception:
                pass
        self.preview.configure(image="", text=tr("no_image_selected"))
        self.preview_photo = None

    def _sync_fitzgerald_from_typology(self) -> None:
        typology_id = self.typology_id_by_label.get(self.typology_var.get().strip(), "none")
        cat = category_for_typology(typology_id)
        self.cell.fitzgerald_category = cat
        if self.fitz_var.get():
            color = config.FITZGERALD_COLORS.get(cat, config.FITZGERALD_COLORS["none"])
            self.fitz_summary_var.set(f"{cat} — {color}")
        else:
            self.fitz_summary_var.set(tr("state_off"))

    def apply(self) -> None:
        self.cell.text = visible_text(self.text_var.get(), uppercase=False)
        self.cell.tts_enabled = self.tts_var.get()
        self.cell.fitzgerald_enabled = self.fitz_var.get()
        self.cell.key_typology = self.typology_id_by_label.get(self.typology_var.get().strip(), "none")
        apply_typology_to_cell(self.cell)
        try:
            self.on_save(self.cell)
        except Exception as e:
            msg = tr("msg_apply_changes_error")
            self.dialogs.error(tr("dialog_edit_cell"), f"{msg}\n\n{e}", parent=self)
            return
        self._safe_destroy()

class SceneEditorDialog(_BaseDialog):
    def __init__(self, master, scene: Scene, on_save: Callable[[Scene], None]):
        super().__init__(master, tr("dialog_scene_properties"), 640, 680)
        self.scene = Scene.from_dict(scene.to_dict())
        self.on_save = on_save
        self.preview_photo = None

        container = ttk.Frame(self, padding=12)
        container.grid(sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.columnconfigure(1, weight=1)
        container.columnconfigure(2, weight=1)

        self._section_label(container, 0, 1, "scene_section")
        ttk.Label(container, text=tr("title")).grid(row=1, column=0, sticky="w")
        self.title_var = tk.StringVar(value=self.scene.title)
        ttk.Entry(container, textvariable=self.title_var, width=40).grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 8))

        ttk.Label(container, text=tr("category")).grid(row=3, column=0, sticky="w")
        self.category_choices = [
            (category["id"], tr(vocabulary_translation_key(category["id"])))
            for column in get_vocabulary_category_columns()
            for category in column
        ]
        self.category_label_to_id = {label: category_id for category_id, label in self.category_choices}
        initial_category = get_vocabulary_category(getattr(self.scene, "scene_focus_category_id", None))
        initial_label = tr(vocabulary_translation_key(initial_category["id"]))
        self.scene_category_var = tk.StringVar(value=initial_label)
        self.scene_category_combo = ttk.Combobox(
            container,
            textvariable=self.scene_category_var,
            values=[label for _category_id, label in self.category_choices],
            state="readonly",
            width=38,
        )
        self.scene_category_combo.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(0, 8))

        ttk.Label(container, text=tr("specific_topic")).grid(row=5, column=0, sticky="w")
        self.scene_specific_topic_var = tk.StringVar(value=getattr(self.scene, "scene_specific_topic", "") or "")
        ttk.Entry(container, textvariable=self.scene_specific_topic_var, width=40).grid(row=6, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        ttk.Label(container, text=tr("clinician_quick_annotations"), foreground="#555555").grid(row=7, column=0, columnspan=3, sticky="w", pady=(0, 10))

        self._section_label(container, 8, 2, "image_section")
        image_buttons = ttk.Frame(container)
        image_buttons.grid(row=9, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Button(image_buttons, text=tr("select_image"), command=self.choose_image).pack(side=tk.LEFT)
        ttk.Button(image_buttons, text=tr("arasaac_open_button"), command=self.open_arasaac_search).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(image_buttons, text=tr("remove_image"), command=self.clear_image).pack(side=tk.LEFT, padx=(6, 0))

        self._section_label(container, 10, 3, "audio_section")
        audio_buttons = ttk.Frame(container)
        audio_buttons.grid(row=11, column=0, columnspan=3, sticky="w", pady=(0, 4))
        ttk.Button(audio_buttons, text=tr("select_audio"), command=self.choose_audio).pack(side=tk.LEFT)
        ttk.Button(audio_buttons, text=tr("record_audio_button"), command=self.record_scene_audio).pack(side=tk.LEFT, padx=(6, 0))
        self.audio_preview_button = ttk.Button(audio_buttons, text=tr("play_preview_button"), command=self.play_scene_audio_preview)
        self.audio_preview_button.pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(audio_buttons, text=tr("remove_audio"), command=self.clear_audio).pack(side=tk.LEFT, padx=(6, 0))
        self.audio_label = ttk.Label(container, text=Path(self.scene.scene_audio).name if self.scene.scene_audio else tr("no_audio"))
        self.audio_label.grid(row=12, column=0, columnspan=3, sticky="w", pady=(0, 8))

        self._section_label(container, 13, 4, "preview_section")
        self.preview = ttk.Label(container, relief=tk.SUNKEN, text=tr("scene_no_image"), anchor="center")
        self.preview.grid(row=14, column=0, columnspan=3, sticky="nsew", ipady=16)

        button_frame = ttk.Frame(container)
        button_frame.grid(row=15, column=0, columnspan=3, sticky="e", pady=(10, 0))
        ttk.Button(button_frame, text=tr("cancel"), command=self.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(button_frame, text=tr("apply"), command=self.apply).pack(side=tk.RIGHT)

        self._update_preview()
        self._refresh_scene_audio_preview_button()

    def _section_label(self, parent, row: int, number: int, label_key: str) -> None:
        ttk.Label(
            parent,
            text=f"{number}  {tr(label_key)}",
            font=("Arial", 10, "bold"),
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(4, 5))

    def choose_image(self) -> None:
        path = self._browse_open(filetypes=config.SUPPORTED_IMAGE_TYPES)
        if path:
            path_obj = Path(path)
            self.scene.background_image = str(path_obj)
            self._update_preview()

    def clear_image(self) -> None:
        self.scene.background_image = ""
        self._update_preview()

    def open_arasaac_search(self) -> None:
        ArasaacSearchDialog(self, initial_query="", on_select=self._apply_arasaac_image)

    def _apply_arasaac_image(self, path: str) -> None:
        if path:
            path_obj = Path(path)
            self.scene.background_image = str(path_obj)
            self._update_preview()

    def choose_label_bg(self) -> None:
        color = colorchooser.askcolor(color=self.label_bg_var.get(), parent=self, title=tr("hotspot_label_bg_dialog"))[1]
        if color:
            self.label_bg_var.set(color)
            self.label_bg_preview.configure(bg=color)

    def choose_label_fg(self) -> None:
        color = colorchooser.askcolor(color=self.label_fg_var.get(), parent=self, title=tr("hotspot_label_fg_dialog"))[1]
        if color:
            self.label_fg_var.set(color)
            self.label_fg_preview.configure(bg=color, fg="white" if color.lower() == "#000000" else "black")

    def choose_audio(self) -> None:
        path = self._browse_open(filetypes=config.SUPPORTED_AUDIO_TYPES)
        if path:
            path_obj = Path(path)
            self.scene.scene_audio = str(path_obj)
            self.audio_label.configure(text=path_obj.name)
            self._refresh_scene_audio_preview_button()

    def clear_audio(self) -> None:
        self.scene.scene_audio = ""
        self.audio_label.configure(text=tr("no_audio"))
        self._refresh_scene_audio_preview_button()

    def _refresh_scene_audio_preview_button(self) -> None:
        try:
            has_audio = bool(self.scene.scene_audio and Path(self.scene.scene_audio).exists())
            self.audio_preview_button.configure(state="normal" if has_audio else "disabled")
        except Exception:
            pass

    def _recording_path_for_scene_audio(self) -> Path:
        from app.services.audio_recording_service import recording_path_for_hotspot
        return recording_path_for_hotspot(getattr(self.scene, "id", None), "scene_audio")

    def record_scene_audio(self) -> None:
        RecordHotspotAudioDialog(
            self,
            destination_factory=self._recording_path_for_scene_audio,
            on_recorded=self._apply_recorded_scene_audio,
            title_key="record_scene_audio",
        )

    def _apply_recorded_scene_audio(self, path: Path) -> None:
        if path:
            self.scene.scene_audio = str(Path(path))
            self.audio_label.configure(text=Path(path).name)
            self._refresh_scene_audio_preview_button()

    def play_scene_audio_preview(self) -> None:
        path = Path(self.scene.scene_audio or "")
        if not path.exists():
            self.dialogs.warning(tr("play_preview_unavailable"), tr("play_preview_missing"), parent=self)
            return
        from app.audio import AudioManager
        if not AudioManager().play_file(str(path)):
            self.dialogs.error(tr("play_preview_unavailable"), tr("play_preview_failed"), parent=self)

    def _update_preview(self) -> None:
        if self.scene.background_image and Path(self.scene.background_image).exists():
            try:
                image = Image.open(self.scene.background_image).convert("RGBA")
                image.thumbnail(config.MAX_SCENE_EDITOR_PREVIEW, Image.LANCZOS)
                self.preview_photo = ImageTk.PhotoImage(image, master=self.preview)
                self.preview.configure(image=self.preview_photo, text="")
                self.preview.image = self.preview_photo
                return
            except Exception:
                pass
        self.preview.configure(image="", text=tr("no_image_selected"))
        self.preview_photo = None

    def apply(self) -> None:
        scene_number = 1
        try:
            if isinstance(self.scene.id, str) and self.scene.id.startswith("scene_"):
                scene_number = int(self.scene.id.split("_", 1)[1])
        except Exception:
            scene_number = 1
        self.scene.title = visible_text(self.title_var.get(), uppercase=False) or default_scene_title(scene_number)
        selected_category_id = self.category_label_to_id.get(self.scene_category_var.get(), "none")
        selected_category = get_vocabulary_category(selected_category_id)
        if selected_category["id"] == "none":
            self.scene.scene_focus_category_id = None
            self.scene.scene_focus_category_label = None
        else:
            self.scene.scene_focus_category_id = selected_category["id"]
            self.scene.scene_focus_category_label = selected_category["label"]
        self.scene.scene_specific_topic = visible_text(self.scene_specific_topic_var.get(), uppercase=False)
        self.on_save(self.scene)
        self.destroy()


class RecordHotspotAudioDialog(_BaseDialog):
    def __init__(self, master, destination_factory: Callable[[], Path], on_recorded: Callable[[Path], None], recorder_factory=None, audio_player=None, title_key: str = "record_hotspot_audio"):
        super().__init__(master, tr(title_key), 520, 210)
        self.destination_factory = destination_factory
        self.on_recorded = on_recorded
        self.recorder_factory = recorder_factory
        self._session = None
        self._recorded_path: Path | None = None
        self.audio_player = audio_player

        container = ttk.Frame(self, padding=12)
        container.grid(sticky="nsew")
        container.columnconfigure(0, weight=1)

        self.status_label = ttk.Label(container, text=tr("start_recording"), wraplength=460)
        self.status_label.grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 8))
        ttk.Label(container, text=tr("recording_input_hint"), wraplength=460, foreground="#666666").grid(row=1, column=0, columnspan=5, sticky="w", pady=(0, 12))

        self.start_button = ttk.Button(container, text=tr("start_recording_button"), command=self.start_recording)
        self.start_button.grid(row=2, column=0, sticky="w")
        self.stop_button = ttk.Button(container, text=tr("stop_recording_button"), command=self.stop_recording, state="disabled")
        self.stop_button.grid(row=2, column=1, sticky="w", padx=(8, 0))
        self.preview_button = ttk.Button(container, text=tr("play_preview_button"), command=self.play_preview, state="disabled")
        self.preview_button.grid(row=2, column=2, sticky="w", padx=(8, 0))
        self.use_button = ttk.Button(container, text=tr("use_recording"), command=self.use_recording, state="disabled")
        self.use_button.grid(row=2, column=3, sticky="w", padx=(8, 0))
        ttk.Button(container, text=tr("cancel_recording_button"), command=self.cancel).grid(row=2, column=4, sticky="e", padx=(8, 0))

        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def start_recording(self) -> None:
        try:
            destination = self.destination_factory()
            recorder_factory = self.recorder_factory
            if recorder_factory is None:
                from app.services.audio_recording_service import WavRecordingSession
                recorder_factory = WavRecordingSession
            self._session = recorder_factory(destination)
            self._session.start()
            self._recorded_path = Path(destination)
            self.status_label.configure(text=tr("recording_status"))
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
        except Exception as exc:
            self._session = None
            self._recorded_path = None
            self.dialogs.error(tr("recording_failed"), str(exc), parent=self)

    def stop_recording(self) -> None:
        if self._session is None:
            return
        try:
            path = Path(self._session.stop())
            self._session = None
            self.status_label.configure(text=tr("audio_recorded"))
            self._recorded_path = path
            self.preview_button.configure(state="normal")
            self.use_button.configure(state="normal")
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
        except Exception as exc:
            self._session = None
            self.dialogs.error(tr("recording_failed"), str(exc), parent=self)
            try:
                self.start_button.configure(state="normal")
                self.stop_button.configure(state="disabled")
            except Exception:
                pass


    def _play_audio_file(self, path: str | Path) -> bool:
        player = self.audio_player
        if player is None:
            from app.audio import AudioManager
            player = AudioManager()
            self.audio_player = player
        return bool(player.play_file(str(path)))

    def play_preview(self) -> None:
        path = Path(self._recorded_path or "")
        if not path.exists():
            self.dialogs.warning(tr("play_preview_unavailable"), tr("play_preview_missing"), parent=self)
            return
        if not self._play_audio_file(path):
            self.dialogs.error(tr("play_preview_unavailable"), tr("play_preview_failed"), parent=self)


    def use_recording(self) -> None:
        path = Path(self._recorded_path or "")
        if not path.exists():
            self.dialogs.warning(tr("play_preview_unavailable"), tr("play_preview_missing"), parent=self)
            return
        self.on_recorded(path)
        self.destroy()
    def cancel(self) -> None:
        if self._session is not None:
            try:
                self._session.cancel(remove_file=True)
            except Exception:
                pass
            self._session = None
        self.destroy()

class HotspotEditorDialog(_BaseDialog):
    def __init__(self, master, hotspot: HotspotData, scene_choices: list[tuple[str, str]], on_save: Callable[[HotspotData], None], on_delete: Callable[[HotspotData], None] | None = None, on_cancel: Callable[[], None] | None = None, anchor_widget=None, scene_id: str = "", project_path: str = ""):
        super().__init__(master, tr("hotspot_dialog_title"), 680, 620)
        self.hotspot = HotspotData.from_dict(hotspot.to_dict())
        self.scene_choices = list(scene_choices or [])
        self.on_save = on_save
        self.on_delete = on_delete
        self.on_cancel = on_cancel
        self.anchor_widget = anchor_widget
        self.scene_id = scene_id
        self.project_path = project_path

        container = ttk.Frame(self, padding=12)
        container.grid(sticky="nsew")
        container.columnconfigure(1, weight=1)

        ttk.Label(container, text=tr("hotspot_insert_text")).grid(row=0, column=0, sticky="w")
        self.text_var = tk.StringVar(value=self.hotspot.text)
        self.text_entry = ttk.Entry(container, textvariable=self.text_var, width=48)
        self.text_entry.grid(row=0, column=1, sticky="ew", pady=(0, 8))

        ttk.Label(container, text=tr("hotspot_audio")).grid(row=1, column=0, sticky="w")
        audio_row = ttk.Frame(container)
        audio_row.grid(row=1, column=1, sticky="ew", pady=(0, 8))
        ttk.Button(audio_row, text=tr("select_audio"), command=self.choose_audio).pack(side=tk.LEFT)
        ttk.Button(audio_row, text=tr("record_audio_button"), command=self.record_audio).pack(side=tk.LEFT, padx=(6, 0))
        self.audio_preview_button = ttk.Button(audio_row, text=tr("play_preview_button"), command=self.play_audio_preview)
        self.audio_preview_button.pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(audio_row, text=tr("remove_audio"), command=self.clear_audio).pack(side=tk.LEFT, padx=(6, 0))

        self.audio_label = ttk.Label(container, text=Path(self.hotspot.audio_path).name if self.hotspot.audio_path else tr("no_audio"), wraplength=360)
        self.audio_label.grid(row=2, column=1, sticky="w", pady=(0, 8))
        self._refresh_audio_preview_button()

        self.tts_var = tk.BooleanVar(value=self.hotspot.tts_enabled)
        ttk.Checkbutton(container, text=tr("hotspot_play_tts"), variable=self.tts_var).grid(row=3, column=1, sticky="w", pady=(0, 8))

        ttk.Label(container, text=tr("hotspot_target_scene")).grid(row=4, column=0, sticky="w")
        self.scene_label_by_id = {sid: name for sid, name in self.scene_choices}
        self.scene_id_by_label = {name: sid for sid, name in self.scene_choices}
        self.scene_values = [name for _, name in self.scene_choices]
        current_scene_label = self.scene_label_by_id.get(self.hotspot.target_scene_id, self.scene_values[0] if self.scene_values else "-")
        self.target_scene_var = tk.StringVar(value=current_scene_label)
        ttk.Combobox(container, textvariable=self.target_scene_var, values=self.scene_values, state="readonly", width=42).grid(row=4, column=1, sticky="ew", pady=(0, 8))

        self.visible_var = tk.BooleanVar(value=self.hotspot.visible_in_design)
        ttk.Checkbutton(container, text=tr("hotspot_visible_user"), variable=self.visible_var).grid(row=5, column=1, sticky="w", pady=(0, 8))

        self._build_visible_text_section(container, row=6)
        self._build_vocabulary_section(container, row=7)

        button_bar = ttk.Frame(container)
        button_bar.grid(row=8, column=0, columnspan=2, sticky="e", pady=(4, 0))
        ttk.Button(button_bar, text=tr("apply"), command=self.apply).pack(side=tk.LEFT)
        ttk.Button(button_bar, text=tr("cancel"), command=self.cancel).pack(side=tk.LEFT, padx=(6, 0))
        if self.on_delete is not None:
            ttk.Button(button_bar, text=tr("delete"), command=self._delete).pack(side=tk.LEFT, padx=(18, 0))

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.after(40, self._set_compact_dialog_geometry)
        self.after(80, self._focus_text_entry)

    def _set_compact_dialog_geometry(self) -> None:
        self.update_idletasks()
        requested_height = int(self.winfo_reqheight()) + 14
        screen_h = int(self.winfo_screenheight())
        height = max(560, min(requested_height, screen_h - 80))
        if self.anchor_widget is not None:
            self._set_dialog_right_of_widget(self.anchor_widget, 680, height)
        else:
            self._set_dialog_right_of_master(680, height)

    def _build_visible_text_section(self, container, row: int) -> None:
        style_frame = ttk.LabelFrame(container, text=tr("hotspot_visible_text"), padding=(8, 6))
        style_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(4, 8))
        style_frame.columnconfigure(7, weight=1)

        ttk.Label(style_frame, text=tr("hotspot_label_size")).grid(row=0, column=0, sticky="w")
        self.label_size_var = tk.IntVar(value=int(getattr(self.hotspot, "label_font_size", 16) or 16))
        ttk.Spinbox(style_frame, from_=8, to=32, textvariable=self.label_size_var, width=5).grid(row=0, column=1, sticky="w", padx=(6, 18))
        ttk.Label(style_frame, text=tr("display_duration")).grid(row=0, column=2, sticky="w")
        self.label_persistence_seconds_var = tk.IntVar(value=int(getattr(self.hotspot, "label_persistence_seconds", 5) or 5))
        ttk.Spinbox(style_frame, from_=1, to=999, textvariable=self.label_persistence_seconds_var, width=5).grid(row=0, column=3, sticky="w", padx=(6, 4))
        ttk.Label(style_frame, text=tr("seconds")).grid(row=0, column=4, sticky="w", padx=(0, 16))
        self.label_persistence_always_var = tk.BooleanVar(value=bool(getattr(self.hotspot, "label_persistence_always", False)))
        ttk.Checkbutton(style_frame, text=tr("always"), variable=self.label_persistence_always_var).grid(row=0, column=5, sticky="w")

        self.label_bg_var = tk.StringVar(value=getattr(self.hotspot, "label_bg_color", "#FFFFFF") or "#FFFFFF")
        self.label_fg_var = tk.StringVar(value=getattr(self.hotspot, "label_fg_color", "#000000") or "#000000")
        ttk.Label(style_frame, text=tr("hotspot_label_bg")).grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.label_bg_preview = tk.Label(style_frame, textvariable=self.label_bg_var, width=8, bg=self.label_bg_var.get(), relief=tk.SOLID, bd=1)
        self.label_bg_preview.grid(row=1, column=1, sticky="w", padx=(6, 4), pady=(8, 0))
        ttk.Button(style_frame, text=tr("change"), width=8, command=self.choose_label_bg).grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Label(style_frame, text=tr("hotspot_label_fg")).grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.label_fg_preview = tk.Label(style_frame, textvariable=self.label_fg_var, width=8, bg=self.label_fg_var.get(), fg="white" if self.label_fg_var.get().lower() == "#000000" else "black", relief=tk.SOLID, bd=1)
        self.label_fg_preview.grid(row=2, column=1, sticky="w", padx=(6, 4), pady=(6, 0))
        ttk.Button(style_frame, text=tr("change"), width=8, command=self.choose_label_fg).grid(row=2, column=2, sticky="w", pady=(6, 0))

    def _build_vocabulary_section(self, container, row: int) -> None:
        research_frame = ttk.LabelFrame(container, text=tr("research_vocabulary_category"), padding=(8, 6))
        research_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(4, 8))
        for column in range(3):
            research_frame.columnconfigure(column, weight=1)
        current_id = getattr(self.hotspot, "vocabulary_category_id", None) or "none"
        self.vocabulary_category_var = tk.StringVar(value=get_vocabulary_category(current_id)["id"])
        for column, categories in enumerate(get_vocabulary_category_columns()):
            self._build_vocabulary_column(research_frame, categories, column)

    def _build_vocabulary_column(self, parent, categories, column: int) -> None:
        frame = ttk.Frame(parent, padding=(2, 0))
        frame.grid(row=0, column=column, sticky="nsew", padx=(0, 8) if column < 2 else (0, 0))
        for row_idx, category in enumerate(categories):
            ttk.Radiobutton(
                frame,
                text=tr(vocabulary_translation_key(category["id"])),
                value=category["id"],
                variable=self.vocabulary_category_var,
            ).grid(row=row_idx, column=0, sticky="w", pady=1)

    def _focus_text_entry(self) -> None:
        try:
            self.focus_force()
            self.text_entry.focus_set()
            self.text_entry.icursor("end")
        except Exception:
            pass

    def choose_label_bg(self) -> None:
        color = colorchooser.askcolor(color=self.label_bg_var.get(), parent=self, title=tr("hotspot_label_bg_dialog"))[1]
        if color:
            self.label_bg_var.set(color)
            self.label_bg_preview.configure(bg=color)

    def choose_label_fg(self) -> None:
        color = colorchooser.askcolor(color=self.label_fg_var.get(), parent=self, title=tr("hotspot_label_fg_dialog"))[1]
        if color:
            self.label_fg_var.set(color)
            self.label_fg_preview.configure(bg=color, fg="white" if color.lower() == "#000000" else "black")

    def _recording_path_for_hotspot(self) -> Path:
        from app.services.audio_recording_service import recording_path_for_hotspot
        return recording_path_for_hotspot(self.scene_id, getattr(self.hotspot, "id", "") or "hotspot", self.project_path)

    def _apply_recorded_audio(self, path: str | Path) -> None:
        path_obj = Path(path)
        self.hotspot.audio_path = str(path_obj)
        self.audio_label.configure(text=path_obj.name)
        self._refresh_audio_preview_button()

    def _refresh_audio_preview_button(self) -> None:
        try:
            has_audio = bool(str(getattr(self.hotspot, "audio_path", "") or "").strip())
            self.audio_preview_button.configure(state="normal" if has_audio else "disabled")
        except Exception:
            pass

    def _play_audio_file(self, path: str | Path) -> bool:
        from app.audio import AudioManager
        audio = AudioManager()
        return bool(audio.play_file(str(path)))

    def play_audio_preview(self) -> None:
        path = Path(getattr(self.hotspot, "audio_path", "") or "")
        if not path.exists():
            self.dialogs.warning(tr("play_preview_unavailable"), tr("play_preview_missing"), parent=self)
            return
        if not self._play_audio_file(path):
            self.dialogs.error(tr("play_preview_unavailable"), tr("play_preview_failed"), parent=self)

    def record_audio(self) -> None:
        RecordHotspotAudioDialog(self, destination_factory=self._recording_path_for_hotspot, on_recorded=self._apply_recorded_audio)

    def choose_audio(self) -> None:
        path = self._browse_open(filetypes=config.SUPPORTED_AUDIO_TYPES)
        if path:
            path_obj = Path(path)
            self.hotspot.audio_path = str(path_obj)
            self.audio_label.configure(text=path_obj.name)
            self._refresh_audio_preview_button()

    def clear_audio(self) -> None:
        self.hotspot.audio_path = ""
        self.audio_label.configure(text=tr("no_audio"))
        self._refresh_audio_preview_button()

    def _delete(self) -> None:
        if self.on_delete is not None:
            self.on_delete(self.hotspot)
        self.destroy()

    def cancel(self) -> None:
        if self.on_cancel is not None:
            try:
                self.on_cancel()
            except Exception:
                pass
        self.destroy()

    def apply(self) -> None:
        self.hotspot.text = visible_text(self.text_var.get(), uppercase=True)
        self.hotspot.label = self.hotspot.text or self.hotspot.label
        self.hotspot.tts_enabled = bool(self.tts_var.get())
        self.hotspot.visible_in_design = bool(self.visible_var.get())
        self.hotspot.target_scene_id = self.scene_id_by_label.get(self.target_scene_var.get().strip(), "")
        category_var = getattr(self, "vocabulary_category_var", None)
        category = get_vocabulary_category(category_var.get() if category_var is not None else "none")
        if category["id"] == "none":
            self.hotspot.vocabulary_category_id = None
            self.hotspot.vocabulary_category_label = None
            self.hotspot.vocabulary_category_group = None
        else:
            self.hotspot.vocabulary_category_id = category["id"]
            self.hotspot.vocabulary_category_label = category["label"]
            self.hotspot.vocabulary_category_group = category["group"]
        self.hotspot.label_bg_color = self.label_bg_var.get().strip() or "#FFFFFF"
        self.hotspot.label_fg_color = self.label_fg_var.get().strip() or "#000000"
        try:
            self.hotspot.label_font_size = max(8, min(int(self.label_size_var.get()), 32))
        except Exception:
            self.hotspot.label_font_size = 16
        try:
            self.hotspot.label_persistence_seconds = max(1, min(int(self.label_persistence_seconds_var.get()), 999))
        except Exception:
            self.hotspot.label_persistence_seconds = 5
        self.hotspot.label_persistence_always = bool(self.label_persistence_always_var.get())
        self.on_save(self.hotspot)
        self.destroy()


class GridSettingsDialog(_BaseDialog):
    def __init__(self, master, rows: int, cols: int, on_save: Callable[[int, int], None]):
        super().__init__(master, tr("dialog_grid_settings"), 360, 150)
        self.on_save = on_save
        container = ttk.Frame(self, padding=12)
        container.grid(sticky="nsew")
        ttk.Label(container, text=tr("grid_distribution")).grid(row=0, column=0, sticky="w")
        self.grid_var = tk.StringVar(value=f"{rows}x{cols}")
        ttk.Combobox(container, textvariable=self.grid_var, values=config.GRID_PRESET_LABELS, state="readonly", width=12).grid(row=1, column=0, sticky="w", pady=(6, 10))
        button_frame = ttk.Frame(container)
        button_frame.grid(row=2, column=0, sticky="e", pady=(12, 0))
        ttk.Button(button_frame, text=tr("cancel"), command=self.destroy).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Button(button_frame, text=tr("apply"), command=self.apply).pack(side=tk.RIGHT)

    def apply(self) -> None:
        try:
            rows, cols = self.grid_var.get().lower().split("x")
            self.on_save(int(rows), int(cols))
            self.destroy()
        except Exception:
            self.dialogs.warning(tr("configure_grid"), tr("msg_invalid_grid"), parent=self)


class UserSelectionDialog(_BaseDialog):
    def __init__(self, master, users_manager, on_select: Callable[[str], None]):
        super().__init__(master, tr("dialog_select_user"), 420, 320)
        self.users_manager = users_manager
        self.on_select = on_select

        container = ttk.Frame(self, padding=12)
        container.grid(sticky="nsew")

        self.listbox = tk.Listbox(container, width=48, height=10)
        self.listbox.grid(row=0, column=0, columnspan=2, sticky="nsew")
        for uid, data in sorted(self.users_manager.users.items(), key=lambda item: item[0]):
            self.listbox.insert(tk.END, f"{uid} - {data.get('name', '')}")

        ttk.Button(container, text=tr("add_user"), command=self.create_user).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Button(container, text=tr("select_user"), command=self.select).grid(row=1, column=1, sticky="e", pady=(8, 0))

    def create_user(self) -> None:
        user_id = self.users_manager.generate_user_id()
        name = self.dialogs.ask_string(tr("dialog_select_user"), tr("user_name"), parent=self)
        if not name:
            return
        self.users_manager.users[user_id] = {
            "id": user_id,
            "name": name,
            "notes": "",
            "group": "",
            "layout_file": "",
            "date_created": "",
            "last_session_date": "",
            "last_session_end": "",
            "total_sessions": 0,
            "total_key_presses": 0,
            "total_words_inserted": 0,
            "total_time_seconds": 0,
        }
        self.users_manager.save_users_to_csv()
        self.listbox.insert(tk.END, f"{user_id} - {name}")

    def select(self) -> None:
        if not self.listbox.curselection():
            self.dialogs.warning(tr("dialog_select_user"), tr("msg_select_user_required"), parent=self)
            return
        item = self.listbox.get(self.listbox.curselection()[0])
        user_id = item.split(" - ", 1)[0].strip()
        self.on_select(user_id)
        self.destroy()


class TextStyleDialog(_BaseDialog):
    def __init__(self, master, size: int, bold: bool, uppercase: bool, visible: bool, on_save: Callable[[int, bool, bool, bool], None]):
        super().__init__(master, tr("cell_text_style"), 400, 240)
        self.on_save = on_save
        container = ttk.Frame(self, padding=12)
        container.grid(sticky="nsew")
        ttk.Label(container, text=tr("text_size")).grid(row=0, column=0, sticky="w")
        self.size_var = tk.IntVar(value=size)
        ttk.Spinbox(container, from_=8, to=16, textvariable=self.size_var, width=8).grid(row=0, column=1, sticky="w", padx=(10,0))

        self.bold_var = tk.BooleanVar(value=bold)
        ttk.Checkbutton(container, text=tr("bold"), variable=self.bold_var).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10,0))
        self.upper_var = tk.BooleanVar(value=uppercase)
        ttk.Checkbutton(container, text=tr("show_uppercase"), variable=self.upper_var).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6,0))
        self.visible_var = tk.BooleanVar(value=visible)
        ttk.Checkbutton(container, text=tr("show_text_below"), variable=self.visible_var).grid(row=3, column=0, columnspan=2, sticky="w", pady=(6,0))

        ttk.Label(container, text=tr("text_style_hint"), wraplength=340, foreground="#666666").grid(row=4, column=0, columnspan=2, sticky="w", pady=(12,0))

        buttons = ttk.Frame(container)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(16,0))
        ttk.Button(buttons, text=tr("cancel"), command=self.destroy).pack(side=tk.RIGHT, padx=(6,0))
        ttk.Button(buttons, text=tr("apply"), command=self.apply).pack(side=tk.RIGHT)

    def apply(self) -> None:
        size = max(8, min(int(self.size_var.get()), 16))
        self.on_save(size, bool(self.bold_var.get()), bool(self.upper_var.get()), bool(self.visible_var.get()))
        self.destroy()


def show_about_dialog(master, title: str, message: str) -> None:
    dialog = _BaseDialog(master, title, 720, 520)
    container = ttk.Frame(dialog, padding=14)
    container.grid(sticky="nsew")
    container.columnconfigure(0, weight=1)
    body = ttk.Label(container, text=message, justify="left", anchor="w", wraplength=660)
    body.grid(row=0, column=0, sticky="nsew")
    buttons = ttk.Frame(container)
    buttons.grid(row=1, column=0, sticky="e", pady=(14, 0))
    ttk.Button(buttons, text=tr("ok"), command=dialog.destroy).pack(side=tk.RIGHT)
    dialog.wait_window()
