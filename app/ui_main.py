from __future__ import annotations

from pathlib import Path
import sys
import tkinter as tk
import uuid
from tkinter import filedialog, simpledialog, ttk

from PIL import Image, ImageDraw, ImageTk

from app import config
from app.audio import AudioManager
from app.controller import AppController
from app.models import CellData, HotspotData, Scene, StoryProject, normalize_supports
from app.research import ResearchLogger
from app.ui_cells import CellWidget
from app.ui_dialogs import CellEditorDialog, GridSettingsDialog, HotspotEditorDialog, SceneEditorDialog, UserSelectionDialog
from app.ui.ui_scene_manager import SceneManagerPanel
from app.ui.ui_text_style import TextStyleDialog
from app.ui.ui_storyboard import StoryboardDialog
from app.ui.ui_research_diagnostics import show_research_diagnostics_dialog
from app.ui.ui_session_stats import show_session_stats_dialog
from app.users import UsersManager
from app.utils import ensure_dirs, maximize_window
from app.i18n import default_project_name, load_saved_language, set_language, tr
from app.services.session_service import SessionService
from app.services.project_workflow_service import ProjectWorkflowService
from app.services.scene_workflow_service import SceneWorkflowService
from app.services.cell_workflow_service import CellWorkflowService
from app.services.research_workflow_service import ResearchWorkflowService
from app.services.ui_state_service import UIStateService
from app.services.scene_image_view_service import SceneImageViewService
from app.services.lifecycle_service import LifecycleService
from app.services.dialog_service import DialogService
from app.services.hotspot_geometry_service import hotspot_overlaps_any
from app.services.support_state_service import project_has_any_supports, scene_has_supports, support_counts, support_has_content


class SaraApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self._initializing_ui = True
        try:
            self.root.withdraw()
        except Exception:
            pass
        load_saved_language()
        self.root.title(f"{config.APP_TITLE} {getattr(config, 'APP_DISPLAY_VERSION', config.APP_VERSION)}")
        maximize_window(self.root)

        ensure_dirs(
            config.DATA_DIR,
            config.PROJECTS_DIR,
            config.LOGS_DIR,
            config.ASSETS_ICONS_DIR,
            config.ASSETS_IMAGES_DIR,
            config.AUDIO_DIR,
        )
        try:
            config.ensure_runtime_data_files()
        except Exception:
            pass

        self.audio = AudioManager()
        self.users_manager = UsersManager(users_csv_path=config.USERS_CSV)
        self.users_manager.load_users_from_csv()
        self.research = ResearchLogger(
            logs_dir=config.LOGS_DIR,
            schema_version=config.RESEARCH_SCHEMA_VERSION,
            ui_language=getattr(config, "CURRENT_UI_LANGUAGE", getattr(config, "DEFAULT_UI_LANGUAGE", "es")),
            app_name=config.APP_TITLE,
            app_version=config.APP_VERSION,
            author=config.AUTHOR,
        )
        self.research.set_enabled(False, silent=True)
        self.research.set_session_context(mode="Therapist", layout_file="sara")

        self.controller = AppController()
        self.dialogs = DialogService()
        self.session_service = SessionService(self.controller, self.audio, self.research, self.users_manager)
        self.project_workflow = ProjectWorkflowService(self.controller, self.research, self.session_service)
        self.scene_workflow = SceneWorkflowService(self.controller)
        self.cell_workflow = CellWorkflowService(self.controller, self.session_service)
        self.research_workflow = ResearchWorkflowService(self.research, self.users_manager, self.dialogs)
        self.ui_state_service = UIStateService(self.controller)
        self.scene_image_view = SceneImageViewService()
        self.lifecycle_service = LifecycleService(self.audio, self.users_manager, self.research)
        self.scene_image_original = None
        self.scene_photo = None
        self.scene_render_info = None
        self.cell_widgets: list[CellWidget] = []
        self.support_widgets: list[CellWidget] = []
        self.support_item_frames: list[tk.Frame] = []
        self.support_visible_vars: list[tk.BooleanVar] = []
        self.support_visible_checks: list[ttk.Checkbutton] = []
        self._action_button_photos: dict[str, ImageTk.PhotoImage] = {}
        self._toolbar_mode_photo: ImageTk.PhotoImage | None = None
        self.thumbnail_window_start = 0
        self.thumbnail_visible_count = 12
        self._scene_add_photo: ImageTk.PhotoImage | None = None
        self.thumbnail_bar_visible = tk.BooleanVar(value=True)
        self.thumbnail_bottom_position = tk.BooleanVar(
            value=str(getattr(config, "NAVIGATION_STRIP_POSITION", "top")).lower() == "bottom"
        )
        # SaraB: optional right-side visual supports, hidden by default to keep the VSD clean.
        self.support_strip_visible = tk.BooleanVar(value=getattr(config, "SUPPORT_STRIP_DEFAULT_VISIBLE", False))
        self.hotspot_overlay_visible = tk.BooleanVar(value=True)
        self._thumbnail_photos: list[ImageTk.PhotoImage | None] = []
        self.hotspot_edit_mode = False
        self.hotspot_tool_mode = "select"
        self.hotspot_edit_enabled_var = tk.BooleanVar(value=False)
        self.hotspot_drag_start = None
        self.hotspot_drag_state = None
        self.hotspot_preview_rect = None
        self.selected_hotspot_id = ""
        self._hotspot_overlap_warning_open = False
        self._last_response_event: dict | None = None
        self._last_hotspot_event: dict | None = None
        self._last_response_mark = "unmarked"

        self._build_menu()
        self._build_layout()
        self._bind_response_mark_shortcuts()
        self._create_cells()
        self._apply_grid_layout()
        if hasattr(self, "right_panel"):
            self.right_panel.grid_remove()
        self._initializing_ui = False
        self._refresh_all()
        try:
            self.root.update_idletasks()
            self.root.deiconify()
            self.root.lift()
        except Exception:
            pass
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _ask_open_filename(self, **kwargs):
        return filedialog.askopenfilename(parent=self.root, **kwargs)

    def _ask_save_filename(self, **kwargs):
        return filedialog.asksaveasfilename(parent=self.root, **kwargs)

    def _open_project_initial_dir(self) -> str:
        try:
            if getattr(sys, "frozen", False):
                examples_dir = Path(sys.executable).resolve().parent / "Example_projects"
                if examples_dir.exists():
                    return str(examples_dir)
        except Exception:
            pass
        return str(config.PROJECTS_DIR)

    def _response_mark_shortcut_bindings(self) -> dict[str, str]:
        return {
            "<space>": "turn",
            "<plus>": "correct",
            "<KP_Add>": "correct",
            "<minus>": "incorrect",
            "<KP_Subtract>": "incorrect",
            "<z>": "unmarked",
            "<Z>": "unmarked",
            "<t>": "turn",
            "<T>": "turn",
            "<a>": "correct",
            "<A>": "correct",
            "<e>": "incorrect",
            "<E>": "incorrect",
        }

    def _bind_response_mark_shortcuts(self) -> None:
        bindings = self._response_mark_shortcut_bindings()
        for sequence, mark in bindings.items():
            try:
                self.root.bind(sequence, lambda event, value=mark: self._handle_response_mark_shortcut(event, value), add="+")
            except Exception:
                pass

    def _bind_response_mark_shortcuts_to_widget(self, widget) -> None:
        for sequence, mark in self._response_mark_shortcut_bindings().items():
            try:
                widget.bind(sequence, lambda event, value=mark: self._handle_response_mark_shortcut(event, value), add="+")
            except Exception:
                pass

    def _focused_widget_is_text_input(self) -> bool:
        try:
            widget = self.root.focus_get()
        except Exception:
            widget = None
        if widget is None:
            return False
        try:
            widget_class = str(widget.winfo_class()).lower()
        except Exception:
            widget_class = widget.__class__.__name__.lower()
        text_classes = {"entry", "text", "spinbox", "ttk::entry", "ttk::spinbox", "tcombobox", "combobox"}
        return widget_class in text_classes or "entry" in widget_class or "text" in widget_class or "combobox" in widget_class

    def _modal_dialog_is_active(self) -> bool:
        try:
            grabbed = self.root.grab_current()
        except Exception:
            grabbed = None
        return grabbed is not None and grabbed is not self.root

    def _response_mark_shortcuts_allowed(self) -> bool:
        if not bool(getattr(getattr(self, "research", None), "research_enabled", False)):
            return False
        if self._modal_dialog_is_active():
            return False
        if self._focused_widget_is_text_input():
            return False
        return True

    def _handle_response_mark_shortcut(self, event, mark: str):
        if not self._response_mark_shortcuts_allowed():
            return None
        if self._apply_response_mark(mark, annotation_source="keyboard"):
            return "break"
        return None

    def _remember_last_response_event(self, event_data: dict) -> None:
        self._last_response_event = dict(event_data or {})
        self._last_response_mark = self._last_response_event.get("response_mark", "unmarked") or "unmarked"
        # Backward-compatible alias for tests and any older internal code.
        self._last_hotspot_event = self._last_response_event
        self._refresh_response_mark_status()

    def _remember_last_hotspot_event(self, hotspot, result) -> None:
        if not bool(getattr(getattr(self, "research", None), "research_enabled", False)):
            self._last_response_event = None
            self._last_hotspot_event = None
            self._refresh_response_mark_status()
            return
        hotspot_label = (
            str(getattr(hotspot, "label", "") or "").strip()
            or str(getattr(result, "inserted_text", "") or "").strip()
            or str(getattr(hotspot, "text", "") or "").strip()
            or str(getattr(hotspot, "id", "") or "").strip()
        )
        self._remember_last_response_event({
            "response_type": "hotspot",
            "event_id": f"hotspot_{uuid.uuid4().hex[:12]}",
            "hotspot_id": str(getattr(hotspot, "id", "") or ""),
            "hotspot_label": hotspot_label,
            "response_label": hotspot_label,
            "scene_id": str(getattr(self.current_scene, "id", "") or ""),
            "scene_title": str(getattr(self.current_scene, "title", "") or ""),
            "scene_index": self.current_scene_index,
            "response_mark": "unmarked",
        })

    def _event_to_image_response_xy(self, event):
        info = self.scene_render_info or {}
        image_x = int(info.get("image_x", 0))
        image_y = int(info.get("image_y", 0))
        display_w = int(info.get("display_width", 0))
        display_h = int(info.get("display_height", 0))
        if display_w <= 0 or display_h <= 0:
            return None
        raw_x = getattr(event, "x", 0)
        raw_y = getattr(event, "y", 0)
        local_x = raw_x - image_x
        local_y = raw_y - image_y
        if local_x < 0 or local_y < 0 or local_x > display_w or local_y > display_h:
            return None
        return {
            "click_x": int(local_x),
            "click_y": int(local_y),
            "x_norm": round(local_x / max(display_w, 1), 6),
            "y_norm": round(local_y / max(display_h, 1), 6),
        }

    def _remember_image_response_click(self, event) -> bool:
        if not bool(getattr(getattr(self, "research", None), "research_enabled", False)):
            return False
        coords = self._event_to_image_response_xy(event)
        if coords is None:
            return False
        event_id = f"image_click_{uuid.uuid4().hex[:12]}"
        response_label = tr("image_response_click_label")
        try:
            self.research.log_event(
                action="image_response_click",
                event_id=event_id,
                key_raw="image_response_click",
                key_type="image_response",
                scene_id=str(getattr(self.current_scene, "id", "") or ""),
                scene_title=str(getattr(self.current_scene, "title", "") or ""),
                scene_index=self.current_scene_index,
                click_x=coords["click_x"],
                click_y=coords["click_y"],
                x_norm=coords["x_norm"],
                y_norm=coords["y_norm"],
                response_mark="unmarked",
                user_id=getattr(self.users_manager, "current_user_id", "") or "",
                user_name=self.users_manager.get_current_user_name() or "",
            )
        except Exception:
            return False
        self._remember_last_response_event({
            "response_type": "image_click",
            "event_id": event_id,
            "hotspot_id": "",
            "hotspot_label": "",
            "response_label": response_label,
            "scene_id": str(getattr(self.current_scene, "id", "") or ""),
            "scene_title": str(getattr(self.current_scene, "title", "") or ""),
            "scene_index": self.current_scene_index,
            "response_mark": "unmarked",
            **coords,
        })
        return True

    def _clear_last_hotspot_event(self) -> None:
        self._last_response_event = None
        self._last_hotspot_event = None
        self._refresh_response_mark_status()

    def _apply_response_mark(self, mark: str, annotation_source: str = "keyboard") -> bool:
        normalized = str(mark or "").strip().lower()
        if normalized not in {"unmarked", "turn", "correct", "incorrect"}:
            return False
        last_event = getattr(self, "_last_response_event", None) or getattr(self, "_last_hotspot_event", None)
        if last_event:
            last_event["response_mark"] = normalized
        self._last_response_mark = normalized
        scene = getattr(self, "current_scene", None)
        try:
            self.research.log_event(
                action="response_mark_annotation",
                event_id=f"annotation_{uuid.uuid4().hex[:12]}",
                key_raw=(last_event or {}).get("response_label", "") or (last_event or {}).get("hotspot_label", "") or "manual_session_mark",
                key_type="response_mark",
                scene_id=(last_event or {}).get("scene_id", "") or str(getattr(scene, "id", "") or ""),
                scene_title=(last_event or {}).get("scene_title", "") or str(getattr(scene, "title", "") or ""),
                scene_index=(last_event or {}).get("scene_index", self.current_scene_index),
                hotspot_id=(last_event or {}).get("hotspot_id", ""),
                hotspot_label=(last_event or {}).get("hotspot_label", ""),
                annotated_event_id=(last_event or {}).get("event_id", ""),
                response_mark=normalized,
                annotation_source=annotation_source,
                user_id=getattr(self.users_manager, "current_user_id", "") or "",
                user_name=self.users_manager.get_current_user_name() or "",
            )
        except Exception:
            pass
        self._refresh_response_mark_status()
        return True

    def _refresh_response_mark_status(self) -> None:
        if not hasattr(self, "response_mark_status_label"):
            return
        research_on = bool(getattr(getattr(self, "research", None), "research_enabled", False))
        if not research_on:
            try:
                self.response_mark_status_var.set(" ")
                self.response_mark_status_label.grid(row=1, column=0, columnspan=10, sticky="w", pady=(2, 0))
            except Exception:
                pass
            return
        last_event = getattr(self, "_last_response_event", None) or getattr(self, "_last_hotspot_event", None)
        if not last_event:
            text = tr(
                "response_mark_no_response_status",
                mark=tr(f"response_mark_{getattr(self, '_last_response_mark', 'unmarked')}"),
            )
        else:
            text = tr(
                "response_mark_status",
                hotspot=last_event.get("response_label", "") or last_event.get("hotspot_label", "") or "-",
                mark=tr(f"response_mark_{last_event.get('response_mark', getattr(self, '_last_response_mark', 'unmarked'))}"),
            )
        try:
            self.response_mark_status_var.set(text)
            self.response_mark_status_label.grid(row=1, column=0, columnspan=10, sticky="w", pady=(2, 0))
        except Exception:
            pass

    # ------------------------------
    # UI construction
    # ------------------------------
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label=tr("new_project"), command=self.new_project)
        file_menu.add_command(label=tr("open_project"), command=self.open_project)
        file_menu.add_command(label=tr("save_project"), command=self.save_project)
        file_menu.add_command(label=tr("save_project_as"), command=self.save_project_as)
        file_menu.add_separator()
        file_menu.add_command(label=tr("exit"), command=self.on_close)
        menubar.add_cascade(label=tr("menu_file"), menu=file_menu)

        mode_menu = tk.Menu(menubar, tearoff=0)
        mode_menu.add_command(label=tr("mode_design"), command=lambda: self.set_mode("design"))
        mode_menu.add_command(label=tr("mode_user"), command=lambda: self.set_mode("user"))
        menubar.add_cascade(label=tr("menu_mode"), menu=mode_menu)

        scene_menu = tk.Menu(menubar, tearoff=0)
        scene_menu.add_command(label=tr("scene_properties"), command=self.edit_scene)
        scene_menu.add_command(label=tr("configure_grid"), command=self.configure_grid)
        scene_menu.add_command(label=tr("scene_panel"), command=self.open_storyboard)
        scene_menu.add_separator()
        scene_menu.add_checkbutton(label=tr("thumbnails_bottom"), variable=self.thumbnail_bottom_position, command=self._toggle_thumbnail_position)
        scene_menu.add_separator()
        scene_menu.add_checkbutton(label=tr("edit_hotspots"), variable=self.hotspot_edit_enabled_var, command=self.toggle_hotspot_edit_mode)
        scene_menu.add_command(label=tr("edit_selected_hotspot"), command=self.edit_selected_hotspot)
        scene_menu.add_command(label=tr("delete_selected_hotspot"), command=self.delete_selected_hotspot)
        scene_menu.add_separator()
        scene_menu.add_command(label=tr("add_scene"), command=self.add_scene)
        scene_menu.add_command(label=tr("duplicate_scene"), command=self.duplicate_scene)
        scene_menu.add_command(label=tr("delete_scene"), command=self.delete_scene)
        scene_menu.add_separator()
        scene_menu.add_command(label=tr("previous_scene"), command=self.previous_scene)
        scene_menu.add_command(label=tr("next_scene"), command=self.next_scene)
        scene_menu.add_command(label=tr("play_scene_audio"), command=self.play_scene_audio)
        menubar.add_cascade(label=tr("menu_scene"), menu=scene_menu)

        research_menu = tk.Menu(menubar, tearoff=0)
        research_menu.add_command(label=tr("toggle_research"), command=self.toggle_research)
        research_menu.add_command(label=tr("select_user"), command=self.select_user)
        research_menu.add_command(label=tr("session_stats"), command=self.show_session_stats)
        research_menu.add_command(label=tr("research_diagnostics"), command=self.show_research_diagnostics)
        research_menu.add_command(label=tr("save_session_summary"), command=self.force_session_summary)
        self.research_menu_label = tr("menu_research")
        menubar.add_cascade(label=self.research_menu_label, menu=research_menu)
        self.research_menu = research_menu

        language_menu = tk.Menu(menubar, tearoff=0)
        language_menu.add_command(label=tr("lang_es"), command=lambda: self.set_language("es"))
        language_menu.add_command(label=tr("lang_en"), command=lambda: self.set_language("en"))
        menubar.add_cascade(label=tr("menu_language"), menu=language_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label=tr("about"), command=self.show_about)
        menubar.add_cascade(label=tr("menu_help"), menu=help_menu)

        self.root.config(menu=menubar)
        self.menubar = menubar

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=0)  # top navigation strip by default
        self.root.rowconfigure(2, weight=1)  # main visual scene area
        self.root.rowconfigure(3, weight=0)  # optional bottom navigation strip

        self.toolbar = ttk.Frame(self.root, padding=(12, 4, 12, 2))
        self.toolbar.grid(row=0, column=0, sticky="ew")
        self.toolbar.columnconfigure(0, weight=1)

        self.project_label_var = tk.StringVar()
        self.scene_label_var = tk.StringVar()
        self.mode_label_var = tk.StringVar()
        self.grid_label_var = tk.StringVar()
        self.user_label_var = tk.StringVar(value=tr("user_status", user="—"))
        self.research_label_var = tk.StringVar(value=tr("research_status", state=tr("state_off")))
        self.response_mark_status_var = tk.StringVar(value="")

        self.project_label = ttk.Label(self.toolbar, textvariable=self.project_label_var, font=("Arial", 11, "bold"))
        self.project_label.grid(row=0, column=0, sticky="w")
        self.thumbnail_toggle = ttk.Checkbutton(
            self.toolbar,
            text=tr("navigation_bar_toggle"),
            variable=self.thumbnail_bar_visible,
            command=self._toggle_thumbnail_bar,
        )
        self.thumbnail_toggle.grid(row=0, column=1, sticky="w", padx=(12, 0))
        self.support_toggle = ttk.Checkbutton(
            self.toolbar,
            text=tr("supports_toggle"),
            variable=self.support_strip_visible,
            command=self._toggle_support_strip,
        )
        self.support_toggle.grid(row=0, column=2, sticky="w", padx=(12, 0))
        self._bind_response_mark_shortcuts_to_widget(self.support_toggle)
        self.hotspot_overlay_toggle = ttk.Checkbutton(
            self.toolbar,
            text=tr("show_hotspots_toggle"),
            variable=self.hotspot_overlay_visible,
            command=self._toggle_hotspot_overlay,
        )
        self.hotspot_overlay_toggle.grid(row=0, column=3, sticky="w", padx=(12, 0))
        self.scene_status_label = ttk.Label(self.toolbar, textvariable=self.scene_label_var)
        self.scene_status_label.grid(row=0, column=4, sticky="w", padx=(12, 0))
        self.mode_status_label = ttk.Label(self.toolbar, textvariable=self.mode_label_var)
        self.mode_status_label.grid(row=0, column=5, sticky="w", padx=(12, 0))
        # Sara 0.1.15: visual-scene mode no longer shows grid/table status in the top bar.
        self.grid_status_label = ttk.Label(self.toolbar, textvariable=self.grid_label_var)
        self.grid_status_label.grid_remove()
        self.user_label = ttk.Label(self.toolbar, textvariable=self.user_label_var)
        self.user_label.grid(row=0, column=6, sticky="w", padx=(12, 0))
        self.research_label = ttk.Label(self.toolbar, textvariable=self.research_label_var)
        self.research_label.grid(row=0, column=7, sticky="e", padx=(12, 0))
        self.research_quick_button = tk.Button(
            self.toolbar,
            command=self.toggle_research,
            width=7,
            height=1,
            relief=tk.RAISED,
            bd=1,
            font=("Arial", 9, "bold"),
            bg="#d9d9d9",
            activebackground="#cfcfcf",
            fg="#111111",
            activeforeground="#111111",
            cursor="hand2",
            takefocus=0,
        )
        self.research_quick_button.grid(row=0, column=8, sticky="e", padx=(4, 0))
        self.mode_quick_button = tk.Button(
            self.toolbar,
            command=self._handle_mode_quick_button,
            width=3,
            height=1,
            relief=tk.RIDGE,
            bd=1,
            bg="#d9d9d9",
            activebackground="#cfcfcf",
            fg="#111111",
            activeforeground="#111111",
            cursor="hand2",
            takefocus=0,
            padx=2,
            pady=1,
        )
        self.mode_quick_button.grid(row=0, column=9, sticky="e", padx=(8, 0))
        self.response_mark_status_label = ttk.Label(
            self.toolbar,
            textvariable=self.response_mark_status_var,
            font=("Arial", 9),
        )
        self.response_mark_status_label.grid(row=1, column=0, columnspan=10, sticky="w", pady=(2, 0))
        self.response_mark_status_var.set(" ")

        self.main = ttk.Frame(self.root, padding=(12, 2, 12, 6))
        self.main.grid(row=2, column=0, sticky="nsew")
        self.main.columnconfigure(0, weight=1)  # main visual scene
        self.main.columnconfigure(1, weight=0)  # optional visual supports
        self.main.rowconfigure(0, weight=1)
        self.main.bind("<Configure>", self._on_main_resize)

        self.scene_title_var = tk.StringVar(value="")

        # SaraB: scene thumbnails are top by default. The clinician can move them
        # to the bottom when this better fits the child's visual access profile.
        self.thumbnail_bar = ttk.Frame(self.root, relief=tk.SOLID, borderwidth=1)
        self.thumbnail_bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 4))
        self.thumbnail_bar.grid_propagate(False)
        self.thumbnail_bar.columnconfigure(0, weight=1)
        self.thumbnail_bar.rowconfigure(0, weight=1)

        self.thumbnail_items_frame = ttk.Frame(self.thumbnail_bar)
        self.thumbnail_items_frame.grid(row=0, column=0, sticky="nsew", padx=6)
        self.thumbnail_items_frame.rowconfigure(0, weight=1)
        self.thumbnail_slots: list[dict[str, tk.Widget]] = []
        self._rebuild_thumbnail_slots(self.thumbnail_visible_count)

        self.left_panel = ttk.Frame(self.main)
        self.left_panel.grid(row=0, column=0, sticky="n", padx=(0, 8))
        self.left_panel.grid_propagate(False)
        self.left_panel.columnconfigure(0, weight=1)
        self.left_panel.rowconfigure(0, weight=1)
        self.left_panel.rowconfigure(1, weight=0)

        self.scene_image_frame = ttk.Frame(self.left_panel, relief=tk.SOLID, borderwidth=2)
        self.scene_image_frame.grid(row=0, column=0, sticky="nsew")
        self.scene_image_frame.grid_propagate(False)
        self.scene_image_frame.columnconfigure(0, weight=1)
        self.scene_image_frame.rowconfigure(0, weight=1)

        self.scene_image_label = ttk.Label(self.scene_image_frame, anchor="center", text=tr("scene_no_image"))
        self.scene_image_label.grid(row=0, column=0, sticky="nsew")
        self.scene_image_label.bind("<Configure>", lambda _e: self._render_scene_image())
        self.scene_image_label.bind("<Button-1>", self._on_scene_click)
        self.scene_image_label.bind("<B1-Motion>", self._on_scene_drag)
        self.scene_image_label.bind("<ButtonRelease-1>", self._on_scene_release)
        self.scene_image_label.bind("<Button-3>", self._on_scene_right_click)
        self.scene_image_label.bind("<Motion>", self._on_scene_motion)
        self.scene_image_label.bind("<Leave>", self._on_scene_leave)

        self.hotspot_tools_frame = tk.Frame(self.scene_image_frame, bg=self._panel_bg(), bd=0)
        self.hotspot_tool_buttons: dict[str, tk.Button] = {}
        self._hotspot_tool_photos: dict[str, ImageTk.PhotoImage] = {}
        self._build_hotspot_tool_buttons()
        self._mode_user_photo: ImageTk.PhotoImage | None = None
        self._scene_audio_photo: ImageTk.PhotoImage | None = None
        self._build_return_to_user_button()
        self._build_scene_audio_button()

        self.scene_controls = SceneManagerPanel(
            self.left_panel,
            on_previous=self.previous_scene,
            on_play_scene=self.play_scene_audio,
            on_next=self.next_scene,
            on_modify_scene=self.modify_current_scene,
            on_user_mode=self.return_to_user_mode,
            on_scene_change=self._handle_scene_change,
            on_add_scene=self.add_scene,
            on_duplicate_scene=self.duplicate_scene,
            on_delete_scene=self.delete_scene,
            on_grid_change=self._handle_grid_change,
            on_text_style=self.configure_text_style,
            on_storyboard=self.open_storyboard,
        )
        # Sara 0.1.15: hide scene selector/options under the image to prioritize the scene.
        self.scene_controls.grid(row=1, column=0, sticky="ew", pady=(0, 0))
        self.scene_controls.grid_remove()
        self.prev_button = self.scene_controls.prev_button
        self.play_scene_button = self.scene_controls.play_scene_button
        self.next_button = self.scene_controls.next_button

        self.right_panel = ttk.Frame(self.main)
        self.right_panel.grid(row=1, column=1, sticky="nsew")
        self.right_panel.grid_remove()
        self.right_panel.grid_propagate(False)

        # SaraB: no visible message-composition area.
        # Optional visual supports are placed in a compact right column and are
        # hidden by default. They act as clinician-selected visual supports, not as a grid.
        self.output_buffer = ""

        self.support_bar = ttk.Frame(self.main, relief=tk.FLAT, borderwidth=0)
        self.support_bar.grid(row=0, column=1, sticky="ns", padx=(14, 0), pady=(0, 0))
        # Fixed reserved width: prevents the scene image from jumping when
        # navigating between scenes with and without visual supports.
        self.support_bar.configure(width=int(getattr(config, "SUPPORT_CARD_WIDTH", 180) or 180) + 12)
        self.support_bar.grid_propagate(False)
        self.support_bar.columnconfigure(0, weight=1)
        self.support_bar.rowconfigure(0, weight=1)

        # SaraB 0.1.3: no title in the right support area. The column should feel
        # like optional visual cues, not a second communication grid.
        self.support_items_frame = ttk.Frame(self.support_bar)
        self.support_items_frame.grid(row=0, column=0, sticky="nsew", padx=4, pady=(6, 6))
        self.support_items_frame.columnconfigure(0, weight=1)
        self._create_support_widgets()
        self._toggle_support_strip()

    def _load_plain_icon(self, icon_name: str, icon_size: int, canvas_size: int | None = None) -> ImageTk.PhotoImage | None:
        icon_path = config.ASSETS_ICONS_DIR / f"{icon_name}.png"
        if not icon_path.exists():
            return None
        try:
            canvas_size = int(canvas_size or icon_size)
            image = Image.open(str(icon_path)).convert("RGBA")
            image.thumbnail((icon_size, icon_size), Image.LANCZOS)
            canvas = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 0))
            offset = ((canvas_size - image.width) // 2, (canvas_size - image.height) // 2)
            canvas.paste(image, offset, image)
            return ImageTk.PhotoImage(canvas)
        except Exception:
            return None


    def _panel_bg(self) -> str:
        """Return a safe neutral background color for tk widgets placed on ttk frames."""
        try:
            return str(self.root.cget("background"))
        except Exception:
            return "#f0f0f0"

    def _build_hotspot_tool_buttons(self) -> None:
        specs = [
            ("add", "hotspot_add", "Nuevo hotspot", self.activate_hotspot_create_tool),
            ("select", "hotspot_select", tr("select_move_hotspot"), self.activate_hotspot_select_tool),
            ("edit", "hotspot_edit", tr("edit_selected_hotspot"), self.edit_selected_hotspot),
            ("delete", "hotspot_delete", tr("delete_selected_hotspot"), self.delete_selected_hotspot),
        ]
        for row, (key, icon_name, label, command) in enumerate(specs):
            photo = self._load_plain_icon(icon_name, 40)
            if photo is not None:
                self._hotspot_tool_photos[key] = photo
            btn = tk.Button(
                self.hotspot_tools_frame,
                image=photo if photo is not None else "",
                text="" if photo is not None else label,
                command=command,
                width=44,
                height=44,
                relief=tk.FLAT,
                bd=0,
                bg=self._panel_bg(),
                activebackground=self._panel_bg(),
                cursor="hand2",
                takefocus=0,
            )
            btn.grid(row=row, column=0, padx=0, pady=(0, 6))
            self.hotspot_tool_buttons[key] = btn

    def _build_return_to_user_button(self) -> None:
        photo = self._load_plain_icon("mode_user_play_round", 38)
        self._mode_user_photo = photo
        self.return_user_button = tk.Button(
            self.scene_image_frame,
            image=photo if photo is not None else "",
            text="" if photo is not None else "▶",
            command=self.return_to_user_mode,
            width=38 if photo is not None else 2,
            height=38 if photo is not None else 1,
            relief=tk.FLAT,
            bd=0,
            bg=self._panel_bg(),
            activebackground=self._panel_bg(),
            cursor="hand2",
            takefocus=0,
        )

    def _build_scene_audio_button(self) -> None:
        """Floating scene-level audio button.

        This button belongs to the scene as a whole, not to a hotspot or a
        visual support. It lets the clinician/user play the global narration
        attached to the current scene.
        """
        photo = self._load_plain_icon("altavoz_scene", 42, canvas_size=48)
        if photo is None:
            photo = self._load_plain_icon("altavoz", 42, canvas_size=48)
        self._scene_audio_photo = photo
        self.scene_audio_button = tk.Button(
            self.scene_image_frame,
            image=photo if photo is not None else "",
            text="" if photo is not None else "🔊",
            command=self._handle_scene_audio_button,
            width=48 if photo is not None else 2,
            height=48 if photo is not None else 1,
            relief=tk.FLAT,
            bd=0,
            bg=self._panel_bg(),
            activebackground=self._panel_bg(),
            cursor="hand2",
            takefocus=0,
        )

    def _handle_scene_audio_button(self) -> None:
        """Scene-audio button action.

        In design mode, the button is also an access point for configuring the
        scene narration. If no audio has been attached yet, clicking it opens
        the scene editor. If audio exists, it plays the current narration.
        """
        try:
            has_scene_audio = bool(str(getattr(self.current_scene, "scene_audio", "") or "").strip())
        except Exception:
            has_scene_audio = False
        if self.current_mode == "user" and not has_scene_audio:
            return
        if self.current_mode == "design" and not has_scene_audio:
            self.edit_scene()
            return
        self.play_scene_audio()

    def _refresh_scene_audio_button_visibility(self) -> None:
        if not hasattr(self, "scene_audio_button"):
            return
        try:
            has_scene_audio = bool(str(getattr(self.current_scene, "scene_audio", "") or "").strip())
        except Exception:
            has_scene_audio = False
        # Design mode: always show the button so the clinician can add scene
        # narration from a visible, stable control. User mode: show it only
        # when there is a real audio file configured for the scene.
        should_show = self.current_mode == "design" or has_scene_audio
        if should_show:
            self.scene_audio_button.place(relx=1.0, rely=1.0, x=-18, y=-18, anchor="se")
            self.scene_audio_button.lift()
        else:
            self.scene_audio_button.place_forget()

    def _set_toolbar_mode_icon(self, icon_name: str, command, icon_size: int = 20, canvas_size: int = 24) -> None:
        """Set the top mode button as a stable rectangular button with icon only."""
        if not hasattr(self, "mode_quick_button"):
            return
        photo = self._load_plain_icon(icon_name, icon_size, canvas_size=canvas_size)
        self._toolbar_mode_photo = photo
        try:
            if photo is not None:
                self.mode_quick_button.configure(
                    image=photo,
                    text="",
                    width=34,
                    height=24,
                    command=command,
                    relief=tk.RIDGE,
                    bd=1,
                    bg="#d9d9d9",
                    activebackground="#cfcfcf",
                )
            else:
                self.mode_quick_button.configure(
                    image="",
                    text="▶" if icon_name == "mode_user_play_bw" else "⚙",
                    width=3,
                    height=1,
                    command=command,
                    relief=tk.RIDGE,
                    bd=1,
                    bg="#d9d9d9",
                    activebackground="#cfcfcf",
                )
        except Exception:
            pass

    def _refresh_toolbar_mode_button(self) -> None:
        if not hasattr(self, "mode_quick_button"):
            return
        if self.current_mode == "design":
            # Design mode: icon-only Play button to return to User mode.
            self._set_toolbar_mode_icon("mode_user_play_bw", self.return_to_user_mode, icon_size=18, canvas_size=24)
        else:
            # User mode: icon-only gear button to enter Design mode.
            self._set_toolbar_mode_icon("gear_fine_36", self.modify_current_scene, icon_size=20, canvas_size=24)

    def _handle_mode_quick_button(self) -> None:
        if self.current_mode == "design":
            self.return_to_user_mode()
        else:
            self.modify_current_scene()

    def _refresh_hotspot_tools_visibility(self) -> None:
        if not hasattr(self, "hotspot_tools_frame"):
            return
        if self.current_mode == "design":
            self.hotspot_tools_frame.place(x=12, y=12)
            self.hotspot_tools_frame.lift()
        else:
            self.hotspot_tools_frame.place_forget()
        # The old floating scene play button is deliberately hidden in both modes.
        # Mode changes are now handled by the stable top rectangular icon button.
        if hasattr(self, "return_user_button"):
            self.return_user_button.place_forget()
        self._refresh_scene_audio_button_visibility()

    def _enable_hotspot_editing(self, tool_mode: str = "select") -> None:
        if self.current_mode != "design":
            self.set_mode("design")
        self.hotspot_tool_mode = tool_mode
        self.hotspot_edit_enabled_var.set(True)
        self.hotspot_edit_mode = True
        self.hotspot_drag_start = None
        self.hotspot_drag_state = None
        self.hotspot_preview_rect = None
        self._render_scene_image()
        self._update_scene_cursor()

    def activate_hotspot_create_tool(self) -> None:
        self._enable_hotspot_editing("create")

    def activate_hotspot_select_tool(self) -> None:
        self._enable_hotspot_editing("select")

    def modify_current_scene(self) -> None:
        # Fast just-in-time editing: enter Design mode and prepare a new hotspot.
        if self.current_mode != "design":
            self.set_mode("design")
        self.activate_hotspot_create_tool()

    def return_to_user_mode(self) -> None:
        self.hotspot_drag_start = None
        self.hotspot_drag_state = None
        self.hotspot_preview_rect = None
        self.hotspot_edit_mode = False
        self.hotspot_edit_enabled_var.set(False)
        self.set_mode("user")

    def _generate_backspace_icon(self, icon_path: str, size: int = 256) -> None:
        try:
            image = Image.new("RGBA", (size, size), (255, 255, 255, 0))
            draw = ImageDraw.Draw(image)
            margin = max(18, size // 10)
            radius = max(6, size // 40)
            tip_x = margin
            mid_y = size // 2
            body_left = margin + size // 5
            body_right = size - margin
            top = margin + size // 8
            bottom = size - margin - size // 8
            points = [
                (tip_x, mid_y),
                (body_left, top),
                (body_right, top),
                (body_right, bottom),
                (body_left, bottom),
            ]
            draw.rounded_rectangle((body_left, top, body_right, bottom), radius=radius, outline="black", width=max(10, size // 18))
            draw.polygon(points, outline="black", fill=None)
            draw.line((tip_x, mid_y, body_left, top), fill="black", width=max(10, size // 18))
            draw.line((tip_x, mid_y, body_left, bottom), fill="black", width=max(10, size // 18))
            cross_margin = size // 7
            x1 = body_left + cross_margin
            y1 = top + cross_margin
            x2 = body_right - cross_margin
            y2 = bottom - cross_margin
            cross_w = max(12, size // 16)
            draw.line((x1, y1, x2, y2), fill="black", width=cross_w)
            draw.line((x1, y2, x2, y1), fill="black", width=cross_w)
            image.save(str(icon_path))
        except Exception:
            pass

    def _load_action_icon(self, icon_name: str, icon_size: int) -> ImageTk.PhotoImage | None:
        icon_path = config.ASSETS_ICONS_DIR / f"{icon_name}.png"
        if icon_name == "backspace" and not icon_path.exists():
            self._generate_backspace_icon(icon_path)
        if not icon_path.exists():
            return None
        try:
            image = Image.open(str(icon_path)).convert("RGBA")
            image.thumbnail((icon_size, icon_size), Image.LANCZOS)
            canvas = Image.new("RGBA", (icon_size, icon_size), (255, 255, 255, 0))
            offset = ((icon_size - image.width) // 2, (icon_size - image.height) // 2)
            canvas.paste(image, offset, image if image.mode == "RGBA" else None)
            return ImageTk.PhotoImage(canvas)
        except Exception:
            return None

    def _set_action_button_icon(self, button, icon_name: str, fallback_text: str, icon_size: int = 66) -> None:
        photo = self._load_action_icon(icon_name, icon_size)
        if photo is not None:
            self._action_button_photos[icon_name] = photo
            button.configure(image=photo, text="", compound="center")
        else:
            button.configure(image="", text=fallback_text, width=6)

    def _refresh_action_buttons(self) -> None:
        # SaraB removes the message-composition area and its speak/delete/clear buttons.
        if not all(hasattr(self, name) for name in ("message_speak_button", "message_backspace_button", "message_clear_button")):
            return
        self._set_action_button_icon(self.message_speak_button, "altavoz", tr("read"), icon_size=66)
        self._set_action_button_icon(self.message_backspace_button, "backspace", tr("delete"), icon_size=66)
        self._set_action_button_icon(self.message_clear_button, "papelera", tr("clear"), icon_size=66)

    def _rebuild_thumbnail_slots(self, count: int) -> None:
        if not hasattr(self, "thumbnail_items_frame"):
            return
        for slot in getattr(self, "thumbnail_slots", []):
            try:
                slot["outer"].destroy()
            except Exception:
                pass
        self.thumbnail_slots = []
        for col in range(max(1, count)):
            self.thumbnail_items_frame.columnconfigure(col, weight=1, uniform="thumb")
            outer = tk.Frame(self.thumbnail_items_frame, bd=1, relief=tk.SOLID, bg="#cfcfcf", highlightthickness=0)
            outer.grid(row=0, column=col, sticky="nsew", padx=4, pady=4)
            outer.grid_propagate(False)
            image_label = tk.Label(outer, text="", bg="#eeeeee", bd=0)
            image_label.place(relx=0.5, rely=0.42, anchor="center", relwidth=0.96, relheight=0.72)
            text_label = tk.Label(outer, text="", bg="white", bd=0, font=("Arial", 8, "bold"), anchor="center")
            text_label.place(relx=0.5, rely=0.88, anchor="center", relwidth=0.98, relheight=0.22)
            self.thumbnail_slots.append({"outer": outer, "label": image_label, "text": text_label})

    def _ensure_thumbnail_slot_count(self) -> None:
        # In Design mode one additional slot is reserved for the + button
        # that creates a new scene. In User mode this professional tool is
        # hidden so the scene remains the focus.
        extra_add_slot = 1 if getattr(self, "current_mode", "design") == "design" else 0
        total = max(1, len(self.project.scenes) + extra_add_slot)
        if total != len(getattr(self, "thumbnail_slots", [])):
            self.thumbnail_visible_count = total
            self._rebuild_thumbnail_slots(total)

    def _shift_thumbnail_window(self, delta: int) -> None:
        max_start = max(0, len(self.project.scenes) - self.thumbnail_visible_count)
        new_start = max(0, min(max_start, self.thumbnail_window_start + delta))
        if new_start != self.thumbnail_window_start:
            self.thumbnail_window_start = new_start
            self._render_scene_thumbnails()

    def _ensure_active_thumbnail_visible(self) -> None:
        if self.current_scene_index < self.thumbnail_window_start:
            self.thumbnail_window_start = self.current_scene_index
        elif self.current_scene_index >= self.thumbnail_window_start + self.thumbnail_visible_count:
            self.thumbnail_window_start = self.current_scene_index - self.thumbnail_visible_count + 1
        max_start = max(0, len(self.project.scenes) - self.thumbnail_visible_count)
        self.thumbnail_window_start = max(0, min(max_start, self.thumbnail_window_start))

    def _build_thumbnail_placeholder(self, width: int, height: int) -> Image.Image:
        image = Image.new("RGB", (max(width, 40), max(height, 30)), "#ebebeb")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, image.width - 1, image.height - 1), outline="#d0d0d0")
        return image

    def _load_thumbnail_image(self, scene: Scene, width: int, height: int) -> Image.Image:
        path = getattr(scene, "background_image", "")
        if path:
            try:
                image = Image.open(path).convert("RGB")
                image.thumbnail((max(width - 8, 40), max(height - 8, 30)), Image.LANCZOS)
                return image
            except Exception:
                pass
        return self._build_thumbnail_placeholder(width, height)

    def _set_thumbnail_active_style(self, outer: tk.Frame, is_active: bool) -> None:
        if is_active:
            outer.configure(bg="#2f5fa7", highlightthickness=2, highlightbackground="#2f5fa7", highlightcolor="#2f5fa7")
        else:
            outer.configure(bg="#cfcfcf", highlightthickness=1, highlightbackground="#cfcfcf", highlightcolor="#cfcfcf")

    def _build_scene_add_thumbnail(self, width: int, height: int) -> Image.Image:
        image = Image.new("RGB", (max(width, 82), max(height, 72)), "#f2f2f2")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, image.width - 1, image.height - 1), outline="#cfcfcf")
        icon_path = config.ASSETS_ICONS_DIR / "hotspot_add.png"
        try:
            icon = Image.open(str(icon_path)).convert("RGBA")
            icon.thumbnail((max(34, image.width // 2), max(34, image.height // 2)), Image.LANCZOS)
            offset = ((image.width - icon.width) // 2, max(4, (image.height - icon.height) // 2 - 2))
            image.paste(icon.convert("RGB"), offset, icon)
        except Exception:
            size = min(image.width, image.height) // 3
            cx, cy = image.width // 2, image.height // 2 - 4
            draw.ellipse((cx - size, cy - size, cx + size, cy + size), fill="#d8d8d8", outline="#bcbcbc")
            draw.line((cx - size // 2, cy, cx + size // 2, cy), fill="#111111", width=max(4, size // 5))
            draw.line((cx, cy - size // 2, cx, cy + size // 2), fill="#111111", width=max(4, size // 5))
        return image

    def _bind_scene_thumbnail_events(self, widget, scene_idx: int) -> None:
        widget.bind("<Button-1>", lambda _e, idx=scene_idx: self._handle_scene_change(idx))
        widget.bind("<Button-3>", lambda e, idx=scene_idx: self._show_scene_context_menu(idx, e))

    def _unbind_scene_thumbnail_events(self, widget) -> None:
        widget.unbind("<Button-1>")
        widget.unbind("<Button-3>")

    def _bind_add_scene_thumbnail_events(self, widget) -> None:
        widget.bind("<Button-1>", lambda _e: self.add_scene())
        widget.bind("<Button-3>", lambda e: self._show_add_scene_context_menu(e))

    def _show_add_scene_context_menu(self, event) -> None:
        if getattr(self, "current_mode", "design") != "design":
            return
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=tr("add_scene"), command=self.add_scene)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_scene_context_menu(self, scene_idx: int, event) -> None:
        if getattr(self, "current_mode", "design") != "design":
            return
        if scene_idx < 0 or scene_idx >= len(self.project.scenes):
            return
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=tr("add_scene"), command=self.add_scene)
        menu.add_command(label=tr("duplicate_scene"), command=lambda idx=scene_idx: self.duplicate_scene_at(idx))
        menu.add_command(label=tr("delete_scene"), command=lambda idx=scene_idx: self.delete_scene_at(idx))
        menu.add_separator()
        menu.add_command(label=tr("scene_properties"), command=lambda idx=scene_idx: self.edit_scene_at(idx))
        menu.add_command(label=tr("rename_scene"), command=lambda idx=scene_idx: self.rename_scene_at(idx))
        menu.add_separator()
        menu.add_command(label=tr("move_left"), command=lambda idx=scene_idx: self.move_scene_at(idx, idx - 1))
        menu.add_command(label=tr("move_right"), command=lambda idx=scene_idx: self.move_scene_at(idx, idx + 1))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _render_scene_thumbnails(self) -> None:
        if not hasattr(self, "thumbnail_slots") or not self.thumbnail_bar_visible.get():
            return
        self._ensure_thumbnail_slot_count()
        self.thumbnail_window_start = 0
        total = len(self.project.scenes)
        self._thumbnail_photos = []
        self.thumbnail_bar.update_idletasks()
        inner_width = max(self.thumbnail_items_frame.winfo_width(), self.thumbnail_bar.winfo_width() - 20, 320)
        thumb_width = max(82, int(inner_width / max(self.thumbnail_visible_count, 1)) - 10)
        thumb_height = max(72, self.thumbnail_bar.winfo_height() - 14)

        for slot_idx, slot in enumerate(self.thumbnail_slots):
            scene_idx = self.thumbnail_window_start + slot_idx
            outer = slot["outer"]
            label = slot["label"]
            text_label = slot.get("text")
            outer.configure(width=thumb_width, height=thumb_height)

            if scene_idx < total:
                scene = self.project.scenes[scene_idx]
                image = self._load_thumbnail_image(scene, thumb_width, thumb_height)
                photo = ImageTk.PhotoImage(image)
                self._thumbnail_photos.append(photo)
                label.configure(image=photo, text="", cursor="hand2")
                label.image = photo
                title = str(getattr(scene, "title", "") or f"Escena {scene_idx + 1}").upper()
                if text_label is not None:
                    text_label.configure(text=f"{scene_idx + 1}. {title}", cursor="hand2")
                    self._bind_scene_thumbnail_events(text_label, scene_idx)
                self._bind_scene_thumbnail_events(label, scene_idx)
                self._bind_scene_thumbnail_events(outer, scene_idx)
                self._set_thumbnail_active_style(outer, scene_idx == self.current_scene_index)
                outer.grid()

            elif scene_idx == total and getattr(self, "current_mode", "design") == "design":
                # Final slot: + button to add a new scene. It is visible only
                # in Design mode because scene creation is a professional action.
                image = self._build_scene_add_thumbnail(thumb_width, thumb_height)
                photo = ImageTk.PhotoImage(image)
                self._thumbnail_photos.append(photo)
                label.configure(image=photo, text="", cursor="hand2")
                label.image = photo
                if text_label is not None:
                    text_label.configure(text=tr("add_scene").upper(), cursor="hand2")
                    self._bind_add_scene_thumbnail_events(text_label)
                self._bind_add_scene_thumbnail_events(label)
                self._bind_add_scene_thumbnail_events(outer)
                self._set_thumbnail_active_style(outer, False)
                outer.configure(bg="#e6e6e6", highlightthickness=1, highlightbackground="#bdbdbd", highlightcolor="#bdbdbd")
                outer.grid()

            else:
                label.configure(image="", text="", cursor="")
                label.image = None
                if text_label is not None:
                    text_label.configure(text="", cursor="")
                    self._unbind_scene_thumbnail_events(text_label)
                self._unbind_scene_thumbnail_events(label)
                self._unbind_scene_thumbnail_events(outer)
                self._set_thumbnail_active_style(outer, False)
                outer.grid_remove()

        # Sara shows all available scene thumbnails in the single top strip.

    def _create_cells(self) -> None:
        for idx in range(max(r * c for r, c in config.GRID_PRESETS)):
            widget = CellWidget(self.right_panel, idx, self.activate_cell, self.edit_cell, style_getter=self._cell_style, mode_getter=lambda: self.current_mode)
            self.cell_widgets.append(widget)

    def _create_support_widgets(self) -> None:
        if not hasattr(self, "support_items_frame"):
            return
        max_items = int(getattr(config, "SUPPORT_STRIP_MAX_ITEMS", 3) or 3)
        card_w = int(getattr(config, "SUPPORT_CARD_WIDTH", 150) or 150)
        card_h = int(getattr(config, "SUPPORT_CARD_HEIGHT", 118) or 118)
        gap = int(getattr(config, "SUPPORT_CARD_VERTICAL_GAP_DESIGN", getattr(config, "SUPPORT_CARD_VERTICAL_GAP", 52)) or 52)
        self.support_widgets = []
        self.support_item_frames = []
        self.support_visible_vars = []
        self.support_visible_checks = []

        # SaraB 0.1.5: three stable support positions. The clinician can mark
        # an empty support as visible before adding image/text/audio. Position
        # is meaningful, so User mode preserves slot 1/2/3 instead of packing
        # visible supports upward.
        for idx in range(max_items):
            self.support_items_frame.rowconfigure(idx, weight=0)
            frame = tk.Frame(self.support_items_frame, bg="#f4f4f4", width=card_w, height=card_h + 30)
            frame.grid_propagate(False)
            frame.grid(row=idx, column=0, sticky="ew", padx=0, pady=(0, gap if idx < max_items - 1 else 0))
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=0)
            frame.rowconfigure(1, weight=1)

            visible_var = tk.BooleanVar(value=False)
            check = ttk.Checkbutton(
                frame,
                text=tr("support_visible"),
                variable=visible_var,
                command=lambda i=idx: self._set_support_visibility(i),
            )
            check.grid(row=0, column=0, sticky="w", padx=2, pady=(0, 6))

            widget = CellWidget(
                frame,
                idx,
                self.activate_support,
                self.edit_support,
                style_getter=self._cell_style,
                mode_getter=lambda: self.current_mode,
                fit_mode_getter=lambda: getattr(config, "SUPPORT_IMAGE_FIT_MODE", "cover"),
            )
            widget.configure(width=card_w, height=card_h)
            widget.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

            self.support_item_frames.append(frame)
            self.support_visible_vars.append(visible_var)
            self.support_visible_checks.append(check)
            self.support_widgets.append(widget)

    def _clear_support_widget_cache(self) -> None:
        """Clear all visual support widgets and checkbox variables.

        This is a defensive UI reset used before/after Nuevo proyecto and
        Cargar proyecto so that no support text/image from the previous project
        can remain on screen. It does not modify the project model itself.
        """
        for var in getattr(self, "support_visible_vars", []) or []:
            try:
                var.set(False)
            except Exception:
                pass
        for widget in getattr(self, "support_widgets", []) or []:
            try:
                widget.clear_display()
                widget.configure_placeholder("+", tr("support_placeholder"))
            except Exception:
                pass
        for frame in getattr(self, "support_item_frames", []) or []:
            try:
                frame.grid_remove()
            except Exception:
                pass
        try:
            self._reserve_or_hide_support_bar()
        except Exception:
            try:
                self.support_bar.grid_remove()
            except Exception:
                pass

    def _reset_transient_project_ui_state(self, *, hide_supports: bool = True) -> None:
        """Reset volatile UI state when creating/loading a project.

        Project changes must not carry over cached support widgets, hotspot
        selections, temporary drag state, or internal text buffers from the
        previous project. This prevents dangerous stale variables in clinical
        sessions.
        """
        self._replace_output_text("")
        self.selected_hotspot_id = ""
        self.hotspot_drag_start = None
        self.hotspot_drag_state = None
        self.hotspot_preview_rect = None
        self.hotspot_edit_mode = False
        try:
            self.hotspot_edit_enabled_var.set(False)
        except Exception:
            pass
        self.scene_image_original = None
        self.scene_photo = None
        self.scene_render_info = None
        self._clear_support_widget_cache()
        if hide_supports and getattr(self, "support_strip_visible", None) is not None:
            try:
                self.support_strip_visible.set(False)
            except Exception:
                pass
        self._sync_support_research_context()


    def _current_scene_has_supports(self) -> bool:
        """Return True only when the current scene actually owns supports.

        The support strip is scene-specific. Navigation must not keep showing
        support content merely because the strip was enabled in a previous
        scene. The layout width, however, may remain reserved for stability.
        """
        return scene_has_supports(self.current_scene)

    def _project_has_any_supports(self) -> bool:
        return project_has_any_supports(self.project)

    def _reserve_or_hide_support_bar(self) -> None:
        """Reserve the support column when the project uses supports.

        This keeps the scene image anchored in the same position while moving
        from a scene with supports to another scene without supports.
        """
        if not hasattr(self, "support_bar"):
            return
        reserve = self._project_has_any_supports() or bool(getattr(self, "support_strip_visible", None) and self.support_strip_visible.get())
        if reserve:
            try:
                self.support_bar.configure(width=int(getattr(config, "SUPPORT_CARD_WIDTH", 180) or 180) + 12)
                self.support_bar.grid(row=0, column=1, sticky="ns", padx=(14, 0), pady=(0, 0))
            except Exception:
                pass
        else:
            try:
                self.support_bar.grid_remove()
            except Exception:
                pass

    def _sync_support_strip_for_scene_navigation(self) -> None:
        """Synchronize support content without moving the scene image.

        Supports remain scene-specific. When the current scene has no supports,
        the support content is hidden, but the support-column width is reserved
        if another scene in the project uses supports. This avoids visual jumps
        while navigating.
        """
        try:
            normalize_supports(self.current_scene)
        except Exception:
            pass
        strip_on = bool(getattr(self, "support_strip_visible", None) and self.support_strip_visible.get())
        show = strip_on and self._current_scene_has_supports()
        if show:
            self._render_support_strip()
        else:
            self._clear_support_widget_cache()
            self._reserve_or_hide_support_bar()

    def _set_support_strip_from_current_scene(self) -> None:
        """Set the general support-strip checkbox from the loaded scene.

        Loading a project should show supports only if the loaded project has
        at least one support explicitly marked visible. A new empty project
        remains clean and hidden.
        """
        try:
            normalize_supports(self.current_scene)
        except Exception:
            pass
        supports = list(getattr(self.current_scene, "supports", []) or [])
        show = any(bool(getattr(s, "visible", False)) for s in supports)
        try:
            self.support_strip_visible.set(bool(show))
        except Exception:
            pass
        if not show:
            self._reserve_or_hide_support_bar()

    def _support_has_content(self, cell) -> bool:
        return support_has_content(cell)

    def _support_counts(self) -> dict:
        """Return quantitative support-strip state for research context.

        Values are automatic and do not depend on clinical judgement:
        number of available support slots, number configured with content,
        and number currently presented/marked visible.
        """
        max_items = int(getattr(config, "SUPPORT_STRIP_MAX_ITEMS", 3) or 3)
        strip_on = bool(getattr(self, "support_strip_visible", None) and self.support_strip_visible.get())
        return support_counts(getattr(self, "current_scene", None), strip_on, max_items)

    def _sync_support_research_context(self) -> None:
        try:
            counts = self._support_counts()
            if hasattr(self.research, "set_support_context"):
                self.research.set_support_context(**counts)
        except Exception:
            pass

    def _set_support_visibility(self, idx: int) -> None:
        """Store the clinician visibility flag for one support.

        The checkbox can be used before the support is configured. This lets
        the clinician prepare the visible structure first, then add image/text.
        In User mode, the slot position is preserved instead of moving supports
        upward.
        """
        scene = getattr(self, "current_scene", None)
        supports = list(getattr(scene, "supports", []) or [])
        if 0 <= idx < len(supports):
            try:
                supports[idx].visible = bool(self.support_visible_vars[idx].get())
            except Exception:
                pass
        self._sync_support_research_context()
        self._render_support_strip()
        try:
            self._on_main_resize()
        except Exception:
            pass

    def _toggle_support_strip(self) -> None:
        if not hasattr(self, "support_bar"):
            return
        if self.support_strip_visible.get():
            self._reserve_or_hide_support_bar()
            self._render_support_strip()
        else:
            self._clear_support_widget_cache()
            self._sync_support_research_context()
            self._reserve_or_hide_support_bar()
        self._on_main_resize()

    def _render_support_strip(self) -> None:
        if not hasattr(self, "support_widgets"):
            return

        if not getattr(self, "support_strip_visible", None) or not self.support_strip_visible.get():
            self._clear_support_widget_cache()
            self._sync_support_research_context()
            self._reserve_or_hide_support_bar()
            return

        max_items = min(len(self.support_widgets), int(getattr(config, "SUPPORT_STRIP_MAX_ITEMS", 3) or 3))
        supports = list(getattr(self.current_scene, "supports", []) or [])
        is_design = getattr(self, "current_mode", "design") == "design"
        card_h = int(getattr(config, "SUPPORT_CARD_HEIGHT", 118) or 118)
        design_control_h = int(getattr(config, "SUPPORT_CARD_DESIGN_CONTROL_HEIGHT", 30) or 30)
        gap_design = int(getattr(config, "SUPPORT_CARD_VERTICAL_GAP_DESIGN", getattr(config, "SUPPORT_CARD_VERTICAL_GAP", 52)) or 52)
        gap_user = int(getattr(config, "SUPPORT_CARD_VERTICAL_GAP_USER", getattr(config, "SUPPORT_CARD_VERTICAL_GAP", 52)) or 52)
        gap = gap_design if is_design else gap_user

        any_user_visible = False
        for idx in range(max_items):
            frame = self.support_item_frames[idx]
            widget = self.support_widgets[idx]
            check = self.support_visible_checks[idx]
            visible_var = self.support_visible_vars[idx]

            support = supports[idx] if idx < len(supports) else None
            has_content = self._support_has_content(support)
            stored_visible = bool(getattr(support, "visible", False)) if support is not None else False
            # Important: visibility is independent of content. The clinician may
            # mark an empty slot visible before editing it.
            visible_var.set(bool(stored_visible))

            frame_height = card_h + (design_control_h if is_design else 0)
            frame.configure(height=frame_height)
            frame.grid(row=idx, column=0, sticky="ew", padx=0, pady=(0, gap if idx < max_items - 1 else 0))

            if is_design:
                check.grid(row=0, column=0, sticky="w", padx=2, pady=(0, 4))
                if support is not None and has_content:
                    widget.configure_cell(support)
                else:
                    widget.configure_placeholder("+", tr("support_placeholder_numbered", n=idx + 1))
                widget.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
                continue

            # User mode: preserve the vertical position of each support slot.
            # If a slot is not visible, keep an empty spacer in that position.
            check.grid_remove()
            if stored_visible:
                any_user_visible = True
                if support is not None and has_content:
                    widget.configure_cell(support)
                else:
                    widget.configure_placeholder("+", tr("support_placeholder_numbered", n=idx + 1))
                widget.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
            else:
                widget.grid_remove()

        self._sync_support_research_context()
        if is_design or any_user_visible:
            self._reserve_or_hide_support_bar()
        else:
            self._reserve_or_hide_support_bar()

    def _apply_grid_layout(self) -> None:
        rows, cols = self.project.grid_rows, self.project.grid_cols
        max_rows = max(r for r, _ in config.GRID_PRESETS)
        max_cols = max(c for _, c in config.GRID_PRESETS)
        for col in range(max_cols):
            self.right_panel.columnconfigure(col, weight=0, uniform="cell")
        for row in range(max_rows):
            self.right_panel.rowconfigure(row, weight=0, uniform="cell")
        for col in range(cols):
            self.right_panel.columnconfigure(col, weight=1, uniform="cell")
        for row in range(rows):
            self.right_panel.rowconfigure(row, weight=1, uniform="cell")

        total = self.project.total_cells
        for idx, widget in enumerate(self.cell_widgets):
            if idx < total:
                row = idx // cols
                col = idx % cols
                widget.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
            else:
                widget.grid_forget()

    # ------------------------------
    # Data helpers
    # ------------------------------
    @property
    def project(self) -> StoryProject:
        return self.controller.project

    @property
    def current_mode(self) -> str:
        return self.controller.current_mode

    @current_mode.setter
    def current_mode(self, value: str) -> None:
        self.controller.current_mode = value

    @property
    def current_scene_index(self) -> int:
        return self.controller.current_scene_index

    @current_scene_index.setter
    def current_scene_index(self, value: int) -> None:
        self.controller.current_scene_index = value

    @property
    def current_scene(self) -> Scene:
        return self.controller.current_scene


    def _toggle_hotspot_overlay(self) -> None:
        self._render_scene_image()
        self._update_scene_cursor()

    def _place_thumbnail_bar(self) -> None:
        if not hasattr(self, "thumbnail_bar"):
            return
        if not self.thumbnail_bar_visible.get():
            self.thumbnail_bar.grid_remove()
            return
        if self.thumbnail_bottom_position.get():
            self.thumbnail_bar.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))
        else:
            self.thumbnail_bar.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 4))

    def _toggle_thumbnail_bar(self) -> None:
        self._place_thumbnail_bar()
        if self.thumbnail_bar_visible.get():
            self._render_scene_thumbnails()
        self._on_main_resize()

    def _toggle_thumbnail_position(self) -> None:
        self._place_thumbnail_bar()
        if self.thumbnail_bar_visible.get():
            self._render_scene_thumbnails()
        self._on_main_resize()

    def _handle_scene_change(self, index: int) -> None:
        try:
            if index >= 0 and index != self.current_scene_index:
                self._clear_last_hotspot_event()
                self.controller.select_scene(index)
                self._sync_support_strip_for_scene_navigation()
                self._refresh_all()
        except Exception:
            pass

    def _handle_grid_change(self, value: str) -> None:
        if self.current_mode != "design":
            return
        if self.scene_workflow.apply_grid_label(value):
            self._refresh_all()

    def _cell_style(self) -> dict:
        return self.controller.cell_style_dict()

    def _refresh_research_quick_button(self) -> None:
        if not hasattr(self, "research_quick_button"):
            return
        enabled = bool(getattr(self.research, "research_enabled", False))
        try:
            is_user_mode = getattr(self, "current_mode", "design") == "user"
            self.research_quick_button.configure(
                text=("ON" if enabled else "OFF"),
                bg="#d9d9d9",
                fg="#111111",
                activebackground="#cfcfcf",
                activeforeground="#111111",
                disabledforeground="#555555",
                relief=tk.RIDGE,
                bd=1,
                state=(tk.DISABLED if is_user_mode else tk.NORMAL),
                cursor=("arrow" if is_user_mode else "hand2"),
            )
        except Exception:
            pass

    def _refresh_all(self) -> None:
        try:
            normalize_supports(self.current_scene)
        except Exception:
            pass
        if hasattr(self, "thumbnail_toggle"):
            self.thumbnail_toggle.configure(text=tr("navigation_bar_toggle"))
        if hasattr(self, "support_toggle"):
            self.support_toggle.configure(text=tr("supports_toggle"))
        if hasattr(self, "hotspot_overlay_toggle"):
            self.hotspot_overlay_toggle.configure(text=tr("show_hotspots_toggle"))
        self._apply_mode_visibility()
        header_state = self.ui_state_service.build_header_state(
            self.users_manager,
            self.research,
        )
        self.project_label_var.set(header_state["project"])
        self.scene_title_var.set(header_state["scene_title"])
        self.scene_label_var.set(header_state["scene"])
        self.mode_label_var.set(header_state["mode"])
        self.grid_label_var.set(header_state["grid"])
        self.user_label_var.set(header_state["user"])
        self.research_label_var.set(f"{tr('research')}:")
        self._refresh_research_quick_button()
        self._refresh_response_mark_status()
        self.ui_state_service.refresh_scene_controls(
            self.scene_controls,
            self.project,
            self.current_scene_index,
            self.current_mode,
        )
        # Keep lower scene selector/options hidden in the image-centred layout.
        try:
            self.scene_controls.grid_remove()
        except Exception:
            pass
        self.toolbar.grid()
        self._apply_grid_layout()
        if hasattr(self, "right_panel"):
            self.right_panel.grid_remove()
        self._sync_research_context()
        self._render_scene_image()
        if self.thumbnail_bar_visible.get():
            self._render_scene_thumbnails()
        if getattr(self, "support_strip_visible", None) is not None and self.support_strip_visible.get():
            self._render_support_strip()
        else:
            self._clear_support_widget_cache()
            self._sync_support_research_context()
            self._reserve_or_hide_support_bar()
        self._refresh_cells()
        self._update_navigation_state()
        self._sync_research_text()
        self._refresh_action_buttons()
        self._refresh_toolbar_mode_button()
        self._refresh_hotspot_tools_visibility()


    def _apply_mode_visibility(self) -> None:
        """Show editing/status controls only in Design mode.

        User mode keeps a cleaner top bar: project title, research state/button,
        and the gear button to return to Design mode.
        """
        is_user_mode = getattr(self, "current_mode", "design") == "user"
        # SaraB 0.1.7: Research controls are therapist/researcher-only.
        # In User mode the status may remain visible, but the menu and ON/OFF
        # control must not be actionable by the child/patient.
        menu_state = tk.DISABLED if is_user_mode else tk.NORMAL

        try:
            if is_user_mode:
                if hasattr(self, "thumbnail_toggle"):
                    self.thumbnail_toggle.grid_remove()
                if hasattr(self, "support_toggle"):
                    self.support_toggle.grid_remove()
                if hasattr(self, "hotspot_overlay_toggle"):
                    self.hotspot_overlay_toggle.grid_remove()
                if hasattr(self, "scene_status_label"):
                    self.scene_status_label.grid_remove()
                if hasattr(self, "mode_status_label"):
                    self.mode_status_label.grid_remove()
                if hasattr(self, "user_label"):
                    self.user_label.grid_remove()
            else:
                if hasattr(self, "thumbnail_toggle"):
                    self.thumbnail_toggle.grid(row=0, column=1, sticky="w", padx=(12, 0))
                if hasattr(self, "support_toggle"):
                    self.support_toggle.grid(row=0, column=2, sticky="w", padx=(12, 0))
                if hasattr(self, "hotspot_overlay_toggle"):
                    self.hotspot_overlay_toggle.grid(row=0, column=3, sticky="w", padx=(12, 0))
                    self.hotspot_overlay_toggle.state(["!disabled"])
                if hasattr(self, "scene_status_label"):
                    self.scene_status_label.grid(row=0, column=4, sticky="w", padx=(12, 0))
                if hasattr(self, "mode_status_label"):
                    self.mode_status_label.grid(row=0, column=5, sticky="w", padx=(12, 0))
                if hasattr(self, "user_label"):
                    self.user_label.grid(row=0, column=6, sticky="w", padx=(12, 0))

            if hasattr(self, "research_label"):
                self.research_label.grid(row=0, column=7, sticky="e", padx=(12, 0))
            if hasattr(self, "research_quick_button"):
                self.research_quick_button.grid(row=0, column=8, sticky="e", padx=(4, 0))
            if hasattr(self, "mode_quick_button"):
                self.mode_quick_button.grid(row=0, column=9, sticky="e", padx=(8, 0))

            if hasattr(self, "research_menu"):
                end_idx = self.research_menu.index("end")
                if end_idx is not None:
                    for idx in range(end_idx + 1):
                        self.research_menu.entryconfig(idx, state=menu_state)
            if hasattr(self, "menubar") and hasattr(self, "research_menu_label"):
                try:
                    self.menubar.entryconfig(self.research_menu_label, state=menu_state)
                except Exception:
                    # Fallback for platforms/themes that require the numeric index.
                    try:
                        self.menubar.entryconfig(3, state=menu_state)
                    except Exception:
                        pass
            if hasattr(self, "research_quick_button"):
                try:
                    self.research_quick_button.configure(
                        state=(tk.DISABLED if is_user_mode else tk.NORMAL),
                        cursor=("arrow" if is_user_mode else "hand2"),
                    )
                except Exception:
                    pass
        except Exception:
            pass

    def _refresh_cells(self) -> None:
        """Refresh legacy grid cells safely.

        SaraB no longer uses the old communication-grid cells as its core
        interface. Some projects therefore contain zero legacy cells. The
        hidden grid must never break support editing or scene refresh.
        """
        cells = list(getattr(self.current_scene, "cells", []) or [])
        total = min(int(getattr(self.project, "total_cells", 0) or 0), len(cells), len(self.cell_widgets))
        for idx in range(total):
            self.cell_widgets[idx].configure_cell(cells[idx])
        for idx in range(total, min(int(getattr(self.project, "total_cells", 0) or 0), len(self.cell_widgets))):
            try:
                self.cell_widgets[idx].grid_forget()
            except Exception:
                pass
        if getattr(self, "support_strip_visible", None) is not None and self.support_strip_visible.get():
            self._render_support_strip()

    def _render_scene_image(self) -> None:
        if getattr(self, "_initializing_ui", False):
            return
        self.scene_image_original, self.scene_photo, self.scene_render_info = self.scene_image_view.render(
            self.current_scene,
            self.current_mode,
            self.scene_image_label,
            current_original=self.scene_image_original,
            preview_rect=self.hotspot_preview_rect,
            selected_hotspot_id=self.selected_hotspot_id,
            show_hotspots=bool(self.hotspot_overlay_visible.get()) or bool(self.hotspot_preview_rect),
        )

    def toggle_hotspot_edit_mode(self) -> None:
        enabled = bool(self.hotspot_edit_enabled_var.get())
        if self.current_mode != "design":
            self.hotspot_edit_mode = False
            self.hotspot_edit_enabled_var.set(False)
            self.dialogs.info("Hotspots", tr("hotspot_editor_design_only"), parent=self.root)
            return
        self.hotspot_edit_mode = enabled
        self.hotspot_drag_start = None
        self.hotspot_preview_rect = None
        if not enabled:
            self.selected_hotspot_id = ""
        self.hotspot_drag_state = None
        self._render_scene_image()
        self._update_scene_cursor()

    def _scene_is_empty_image_placeholder(self) -> bool:
        info = self.scene_render_info or {}
        return bool(info.get("no_scene_image")) and self.current_mode == "design"

    def _empty_scene_plus_hit(self, event) -> bool:
        if not self._scene_is_empty_image_placeholder() or event is None:
            return False
        info = self.scene_render_info or {}
        disp_w = int(info.get("display_width") or 0)
        disp_h = int(info.get("display_height") or 0)
        if disp_w <= 0 or disp_h <= 0:
            return False
        plus_size = int(info.get("empty_plus_size") or 92)
        # Accessibility: use a generous hit area around the visual + so the
        # cursor changes earlier and clicking is easier.
        half = max(80, int(plus_size * 0.95))
        cx = disp_w // 2
        cy = disp_h // 2
        ex = int(getattr(event, "x", 0))
        ey = int(getattr(event, "y", 0))
        return (cx - half) <= ex <= (cx + half) and (cy - half) <= ey <= (cy + half)

    def _set_scene_cursor(self, cursor: str = "") -> None:
        try:
            self.scene_image_label.configure(cursor=cursor or "")
        except Exception:
            pass

    def _cursor_for_handle(self, handle: str | None) -> str:
        if handle in {"nw", "se"}:
            return "size_nw_se"
        if handle in {"ne", "sw"}:
            return "size_ne_sw"
        return "fleur"

    def _update_scene_cursor(self, event=None) -> None:
        if event is None:
            try:
                px, py = self.scene_image_label.winfo_pointerxy()
                event = type("_PointerEvent", (), {
                    "x": px - self.scene_image_label.winfo_rootx(),
                    "y": py - self.scene_image_label.winfo_rooty(),
                })()
            except Exception:
                event = None
        if self.current_mode == "design":
            if self._scene_is_empty_image_placeholder():
                self._set_scene_cursor("hand2" if self._empty_scene_plus_hit(event) else "")
                return
            if not self.hotspot_edit_mode:
                self._set_scene_cursor("")
                return
            drag_state = self.hotspot_drag_state or {}
            drag_mode = drag_state.get("mode")
            if drag_mode == "create":
                self._set_scene_cursor("tcross")
                return
            if drag_mode == "move":
                self._set_scene_cursor("fleur")
                return
            if drag_mode == "resize":
                self._set_scene_cursor(self._cursor_for_handle(drag_state.get("handle")))
                return
            if event is not None:
                hotspot = self.scene_image_view.hotspot_hit_test(
                    getattr(self.current_scene, "hotspots", []),
                    self.scene_render_info,
                    getattr(event, "x", 0),
                    getattr(event, "y", 0),
                )
                if hotspot is not None:
                    handle = self.scene_image_view.hotspot_handle_hit_test(
                        hotspot,
                        self.scene_render_info,
                        getattr(event, "x", 0),
                        getattr(event, "y", 0),
                    )
                    self._set_scene_cursor(self._cursor_for_handle(handle))
                    return
            self._set_scene_cursor("tcross")
            return
        if event is not None:
            hotspot = self.scene_image_view.hotspot_hit_test(
                getattr(self.current_scene, "hotspots", []),
                self.scene_render_info,
                getattr(event, "x", 0),
                getattr(event, "y", 0),
            )
            self._set_scene_cursor("hand2" if hotspot is not None else "")
            return
        self._set_scene_cursor("")

    def _on_scene_motion(self, event) -> None:
        self._update_scene_cursor(event)

    def _on_scene_leave(self, _event=None) -> None:
        if self._scene_is_empty_image_placeholder():
            self._set_scene_cursor("")
        elif self.current_mode == "design" and self.hotspot_edit_mode:
            self._set_scene_cursor("tcross")
        else:
            self._set_scene_cursor("")

    def _make_hotspot_context_menu(self, hotspot) -> None:
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=tr("edit_hotspot"), command=lambda h=hotspot: self._open_hotspot_editor(h))
        menu.add_command(label=tr("delete_hotspot"), command=lambda h=hotspot: self._delete_hotspot(h))
        self._hotspot_context_menu = menu

    def _scene_choice_pairs(self):
        pairs = [("", tr("no_target_scene"))]
        for idx, scene in enumerate(list(getattr(self.project, "scenes", []) or []), start=1):
            title = str(getattr(scene, "title", "") or f"Escena {idx}")
            pairs.append((str(getattr(scene, "id", "") or f"scene_{idx}"), f"{idx}. {title}"))
        return pairs

    def _open_hotspot_editor(self, hotspot=None, initial_rect=None) -> None:
        if self.current_mode != "design":
            return
        is_new_hotspot = hotspot is None
        if hotspot is None:
            hotspot = HotspotData(id=f"hotspot_{uuid.uuid4().hex[:8]}")
            if initial_rect:
                hotspot.x = float(initial_rect.get("x", 0.0))
                hotspot.y = float(initial_rect.get("y", 0.0))
                hotspot.width = float(initial_rect.get("width", 0.12))
                hotspot.height = float(initial_rect.get("height", 0.12))
        self.hotspot_preview_rect = None
        self.hotspot_drag_start = None
        self.hotspot_drag_state = None

        def on_save(updated_hotspot):
            existing = list(getattr(self.current_scene, "hotspots", []) or [])
            replaced = False
            for idx, item in enumerate(existing):
                if str(getattr(item, "id", "")) == str(updated_hotspot.id):
                    existing[idx] = updated_hotspot
                    replaced = True
                    break
            if not replaced:
                existing.append(updated_hotspot)
            self.current_scene.hotspots = existing
            self.selected_hotspot_id = str(updated_hotspot.id)
            self._render_scene_image()

        def on_delete(updated_hotspot):
            self._delete_hotspot(updated_hotspot)

        def on_cancel():
            self.hotspot_preview_rect = None
            self.hotspot_drag_start = None
            self.hotspot_drag_state = None
            if is_new_hotspot:
                self.selected_hotspot_id = ""
            self._render_scene_image()
            self._update_scene_cursor()

        dialog = HotspotEditorDialog(
            self.root,
            hotspot,
            self._scene_choice_pairs(),
            on_save=on_save,
            on_delete=on_delete,
            on_cancel=on_cancel,
            anchor_widget=self.scene_image_frame,
        )
        dialog.bind("<Destroy>", lambda _e: self.root.after(0, self._update_scene_cursor), add="+")

    def _delete_hotspot(self, hotspot) -> None:
        items = list(getattr(self.current_scene, "hotspots", []) or [])
        target_id = str(getattr(hotspot, "id", ""))
        removed = False
        kept = []
        for item in items:
            same_id = target_id and str(getattr(item, "id", "")) == target_id
            same_object = item is hotspot
            if not removed and (same_id or same_object):
                removed = True
                continue
            kept.append(item)
        self.current_scene.hotspots = kept
        if self.selected_hotspot_id == str(getattr(hotspot, "id", "")):
            self.selected_hotspot_id = ""
        self.hotspot_drag_state = None
        self.hotspot_preview_rect = None
        self._render_scene_image()
        self._update_scene_cursor()

    def edit_selected_hotspot(self) -> None:
        hotspot = None
        for item in list(getattr(self.current_scene, "hotspots", []) or []):
            if str(getattr(item, "id", "")) == str(self.selected_hotspot_id):
                hotspot = item
                break
        if hotspot is None:
            self.dialogs.info("Hotspots", tr("select_hotspot_first"), parent=self.root)
            return
        self._open_hotspot_editor(hotspot)

    def delete_selected_hotspot(self) -> None:
        hotspot = None
        for item in list(getattr(self.current_scene, "hotspots", []) or []):
            if str(getattr(item, "id", "")) == str(self.selected_hotspot_id):
                hotspot = item
                break
        if hotspot is None:
            self.dialogs.info("Hotspots", tr("no_hotspot_selected"), parent=self.root)
            return
        self._delete_hotspot(hotspot)

    def _event_to_local_scene_xy(self, event):
        info = self.scene_render_info or {}
        image_x = int(info.get("image_x", 0))
        image_y = int(info.get("image_y", 0))
        display_w = int(info.get("display_width", 0))
        display_h = int(info.get("display_height", 0))
        if display_w <= 0 or display_h <= 0:
            return None
        local_x = max(0, min(display_w, getattr(event, "x", 0) - image_x))
        local_y = max(0, min(display_h, getattr(event, "y", 0) - image_y))
        return local_x, local_y, display_w, display_h

    def _current_selected_hotspot(self):
        for item in list(getattr(self.current_scene, "hotspots", []) or []):
            if str(getattr(item, "id", "")) == str(self.selected_hotspot_id):
                return item
        return None

    def _hotspot_overlaps_existing(self, hotspot) -> bool:
        return hotspot_overlaps_any(
            hotspot,
            getattr(self.current_scene, "hotspots", []),
            exclude_id=str(getattr(hotspot, "id", "") or ""),
        )

    def _show_hotspot_overlap_warning(self) -> None:
        if bool(getattr(self, "_hotspot_overlap_warning_open", False)):
            return
        self._hotspot_overlap_warning_open = True
        try:
            try:
                self.root.lift()
                self.root.focus_force()
            except Exception:
                pass
            self.dialogs.warning(
                tr("hotspot_overlap_title"),
                tr("hotspot_overlap_warning"),
                parent=self.root,
            )
        finally:
            self._hotspot_overlap_warning_open = False

    @staticmethod
    def _restore_hotspot_geometry(hotspot, origin: dict) -> None:
        for field in ("x", "y", "width", "height"):
            if field in origin:
                setattr(hotspot, field, float(origin[field]))

    def _event_to_hotspot_rect(self, start_event, end_event):
        info = self.scene_render_info or {}
        image_x = int(info.get("image_x", 0))
        image_y = int(info.get("image_y", 0))
        display_w = int(info.get("display_width", 0))
        display_h = int(info.get("display_height", 0))
        if display_w <= 0 or display_h <= 0:
            return None
        x1 = max(0, min(display_w, getattr(start_event, "x", 0) - image_x))
        y1 = max(0, min(display_h, getattr(start_event, "y", 0) - image_y))
        x2 = max(0, min(display_w, getattr(end_event, "x", 0) - image_x))
        y2 = max(0, min(display_h, getattr(end_event, "y", 0) - image_y))
        left, right = sorted([x1, x2])
        top, bottom = sorted([y1, y2])
        if right - left < 12 or bottom - top < 12:
            return None
        return {
            "x": left / display_w,
            "y": top / display_h,
            "width": (right - left) / display_w,
            "height": (bottom - top) / display_h,
        }

    def _on_scene_drag(self, event) -> None:
        if self.current_mode != "design" or not self.hotspot_edit_mode or self.hotspot_drag_state is None:
            return
        mode = self.hotspot_drag_state.get("mode")
        if mode == "create":
            rect = self._event_to_hotspot_rect(self.hotspot_drag_start, event)
            self.hotspot_preview_rect = rect
            self._render_scene_image()
            self._update_scene_cursor(event)
            return
        hotspot = self.hotspot_drag_state.get("hotspot")
        start_local = self.hotspot_drag_state.get("start_local")
        origin = self.hotspot_drag_state.get("origin") or {}
        local = self._event_to_local_scene_xy(event)
        if hotspot is None or start_local is None or local is None:
            return
        local_x, local_y, display_w, display_h = local
        dx = (local_x - start_local[0]) / max(display_w, 1)
        dy = (local_y - start_local[1]) / max(display_h, 1)
        min_size = 0.03
        resize_handle = self.hotspot_drag_state.get("handle")
        if mode == "move":
            hotspot.x = max(0.0, min(origin.get("x", 0.0) + dx, 1.0 - hotspot.width))
            hotspot.y = max(0.0, min(origin.get("y", 0.0) + dy, 1.0 - hotspot.height))
        elif mode == "resize":
            ox = origin.get("x", hotspot.x)
            oy = origin.get("y", hotspot.y)
            ow = origin.get("width", hotspot.width)
            oh = origin.get("height", hotspot.height)
            if "e" in resize_handle:
                hotspot.width = max(min_size, min(1.0 - ox, ow + dx))
            if "s" in resize_handle:
                hotspot.height = max(min_size, min(1.0 - oy, oh + dy))
            if "w" in resize_handle:
                new_x = max(0.0, min(ox + dx, ox + ow - min_size))
                hotspot.width = max(min_size, (ox + ow) - new_x)
                hotspot.x = new_x
            if "n" in resize_handle:
                new_y = max(0.0, min(oy + dy, oy + oh - min_size))
                hotspot.height = max(min_size, (oy + oh) - new_y)
                hotspot.y = new_y
        self._render_scene_image()
        self._update_scene_cursor(event)

    def _on_scene_release(self, event) -> None:
        if self.current_mode != "design" or not self.hotspot_edit_mode or self.hotspot_drag_state is None:
            return
        mode = self.hotspot_drag_state.get("mode")
        if mode == "create":
            rect = self._event_to_hotspot_rect(self.hotspot_drag_start, event)
            self.hotspot_drag_start = None
            self.hotspot_drag_state = None
            self.hotspot_preview_rect = None
            self.hotspot_drag_state = None
            if rect is None:
                self._render_scene_image()
                self._update_scene_cursor(event)
                return
            candidate = HotspotData(id="__hotspot_overlap_candidate__", **rect)
            if self._hotspot_overlaps_existing(candidate):
                self._render_scene_image()
                self._show_hotspot_overlap_warning()
                self._update_scene_cursor(event)
                return
            self._open_hotspot_editor(initial_rect=rect)
            self._update_scene_cursor()
            return
        drag_state = self.hotspot_drag_state or {}
        hotspot = drag_state.get("hotspot")
        origin = drag_state.get("origin") or {}
        overlaps = hotspot is not None and self._hotspot_overlaps_existing(hotspot)
        if overlaps:
            self._restore_hotspot_geometry(hotspot, origin)
        self.hotspot_drag_state = None
        self.hotspot_drag_start = None
        self.hotspot_preview_rect = None
        self._render_scene_image()
        if overlaps:
            self._show_hotspot_overlap_warning()
        self._update_scene_cursor(event)

    def _on_scene_right_click(self, event) -> None:
        hotspot = self.scene_image_view.hotspot_hit_test(
            getattr(self.current_scene, "hotspots", []),
            self.scene_render_info,
            getattr(event, "x", 0),
            getattr(event, "y", 0),
        )
        if self.current_mode != "design":
            # Sara: in user mode, right-click over the selected hotspot hides
            # the fixed visible label without modifying the hotspot itself.
            if hotspot is not None and str(getattr(hotspot, "id", "")) == str(self.selected_hotspot_id):
                self._clear_hotspot_label_timer()
                self.selected_hotspot_id = ""
                self._render_scene_image()
                self._update_scene_cursor(event)
            return
        if not self.hotspot_edit_mode:
            return
        if hotspot is None:
            self.selected_hotspot_id = ""
            self._render_scene_image()
            self._update_scene_cursor(event)
            return
        self.selected_hotspot_id = str(getattr(hotspot, "id", ""))
        self._render_scene_image()
        self._update_scene_cursor(event)
        self._make_hotspot_context_menu(hotspot)
        try:
            self._hotspot_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._hotspot_context_menu.grab_release()

    def _on_scene_click(self, event) -> None:
        if self.current_mode == "design":
            # In an empty scene, only the central + opens scene editing.
            # The rest of the empty area does nothing and keeps the normal pointer.
            if self._scene_is_empty_image_placeholder():
                if self._empty_scene_plus_hit(event):
                    self.edit_scene()
                return
            if self.hotspot_edit_mode:
                if self.selected_hotspot_id:
                    selected_hotspot = self._current_selected_hotspot()
                    if selected_hotspot is not None:
                        handle = self.scene_image_view.hotspot_handle_hit_test(
                            selected_hotspot,
                            self.scene_render_info,
                            getattr(event, "x", 0),
                            getattr(event, "y", 0),
                        )
                        if handle:
                            local = self._event_to_local_scene_xy(event)
                            self.hotspot_drag_start = event
                            self.hotspot_drag_state = {
                                "mode": "resize",
                                "handle": handle,
                                "hotspot": selected_hotspot,
                                "start_local": (local[0], local[1]) if local else None,
                                "origin": {
                                    "x": float(getattr(selected_hotspot, "x", 0.0)),
                                    "y": float(getattr(selected_hotspot, "y", 0.0)),
                                    "width": float(getattr(selected_hotspot, "width", 0.1)),
                                    "height": float(getattr(selected_hotspot, "height", 0.1)),
                                },
                            }
                            self._render_scene_image()
                            self._update_scene_cursor(event)
                            return
                hotspot = self.scene_image_view.hotspot_hit_test(
                    getattr(self.current_scene, "hotspots", []),
                    self.scene_render_info,
                    getattr(event, "x", 0),
                    getattr(event, "y", 0),
                )
                if hotspot is not None:
                    self.selected_hotspot_id = str(getattr(hotspot, "id", ""))
                    handle = self.scene_image_view.hotspot_handle_hit_test(hotspot, self.scene_render_info, getattr(event, "x", 0), getattr(event, "y", 0))
                    local = self._event_to_local_scene_xy(event)
                    self.hotspot_drag_start = event
                    self.hotspot_drag_state = {
                        "mode": "resize" if handle else "move",
                        "handle": handle,
                        "hotspot": hotspot,
                        "start_local": (local[0], local[1]) if local else None,
                        "origin": {
                            "x": float(getattr(hotspot, "x", 0.0)),
                            "y": float(getattr(hotspot, "y", 0.0)),
                            "width": float(getattr(hotspot, "width", 0.1)),
                            "height": float(getattr(hotspot, "height", 0.1)),
                        },
                    }
                    self._render_scene_image()
                    self._update_scene_cursor(event)
                    return
                self.selected_hotspot_id = ""
                if getattr(self, "hotspot_tool_mode", "select") == "create":
                    self.hotspot_drag_start = event
                    self.hotspot_drag_state = {"mode": "create"}
                else:
                    self.hotspot_drag_start = None
                    self.hotspot_drag_state = None
                self._render_scene_image()
                self._update_scene_cursor(event)
                return
            self.edit_scene()
            return
        hotspot = self.scene_image_view.hotspot_hit_test(
            getattr(self.current_scene, "hotspots", []),
            self.scene_render_info,
            getattr(event, "x", 0),
            getattr(event, "y", 0),
        )
        if hotspot is not None:
            self.activate_hotspot(hotspot)
            return
        self._remember_image_response_click(event)
        return

    def activate_hotspot(self, hotspot) -> None:
        # Sara: keep the clicked hotspot label visible according to the
        # hotspot permanence settings.
        self.selected_hotspot_id = str(getattr(hotspot, "id", ""))
        self._schedule_hotspot_label_hide(hotspot)
        current = ""
        result = self.session_service.activate_hotspot(
            self.project,
            self.current_scene,
            self.current_scene_index,
            self.current_mode,
            hotspot,
            current,
        )
        if getattr(result, "action", "ignored") != "insert":
            self._render_scene_image()
            return
        self._remember_last_hotspot_event(hotspot, result)
        # No visible message accumulation in SaraB. The inserted text remains
        # available in the research log through text_inserted/key_raw.
        self._replace_output_text("")
        self._sync_research_text()
        target_index = self.controller.scene_index_from_id(getattr(result, "target_scene_id", ""))
        if target_index is not None and target_index != self.current_scene_index:
            self.controller.select_scene(target_index)
            self._sync_support_strip_for_scene_navigation()
            self._clear_hotspot_label_timer()
            self.selected_hotspot_id = ""
            self._refresh_all()
        else:
            self._render_scene_image()

    def _clear_hotspot_label_timer(self) -> None:
        if getattr(self, "_hotspot_label_hide_after_id", None):
            try:
                self.root.after_cancel(self._hotspot_label_hide_after_id)
            except Exception:
                pass
            self._hotspot_label_hide_after_id = None

    def _schedule_hotspot_label_hide(self, hotspot) -> None:
        self._clear_hotspot_label_timer()
        if bool(getattr(hotspot, "label_persistence_always", False)):
            return
        try:
            seconds = max(1, int(getattr(hotspot, "label_persistence_seconds", 5) or 5))
        except Exception:
            seconds = 5
        hotspot_id = str(getattr(hotspot, "id", ""))
        def _hide_if_current():
            if self.selected_hotspot_id == hotspot_id:
                self.selected_hotspot_id = ""
                self._hotspot_label_hide_after_id = None
                self._render_scene_image()
        self._hotspot_label_hide_after_id = self.root.after(seconds * 1000, _hide_if_current)

    def _update_navigation_state(self) -> None:
        self.ui_state_service.update_navigation_buttons(
            self.prev_button,
            self.next_button,
            self.current_scene_index,
            len(self.project.scenes),
        )

    def _sync_research_context(self) -> None:
        self.session_service.sync_research_context(
            self.project,
            self.current_scene,
            self.current_scene_index,
            self.current_mode,
        )

    def _get_output_text(self) -> str:
        # SaraB has no visible message-composition area. A small internal
        # buffer is kept only for backward-compatible service calls.
        return getattr(self, "output_buffer", "")

    def _replace_output_text(self, value: str) -> None:
        self.output_buffer = value or ""

    def _sync_research_text(self) -> None:
        text = self._get_output_text()
        self.session_service.sync_research_text(text, mode="Therapist")

    def _on_main_resize(self, _event=None) -> None:
        if getattr(self, "_initializing_ui", False):
            return
        # During startup Tk can emit a Configure event before every panel exists.
        # Ignore those early events instead of interrupting the application.
        required = ("main", "left_panel", "right_panel", "scene_controls", "thumbnail_bar", "scene_image_frame", "support_bar")
        if not all(hasattr(self, name) for name in required):
            return
        self.ui_state_service.resize_main_panel(
            self.main,
            self.left_panel,
            self.right_panel,
            self.scene_controls,
            self.thumbnail_bar,
            self.scene_image_frame,
            self._render_scene_image,
            self._render_scene_thumbnails,
            thumbnail_bar_visible=self.thumbnail_bar_visible.get(),
            support_bar=self.support_bar,
            support_bar_visible=self.support_strip_visible.get(),
            render_support_strip=self._render_support_strip,
        )
        self._refresh_action_buttons()

    def _speak_output_text(self) -> None:
        self.session_service.speak_output_text(
            self.project,
            self.current_scene,
            self.current_scene_index,
            self.current_mode,
            self._get_output_text(),
        )

    def _backspace_output_text(self) -> None:
        new_text = self.session_service.backspace_output_text(
            self.project,
            self.current_scene,
            self.current_scene_index,
            self.current_mode,
            self._get_output_text(),
        )
        if new_text is None:
            return
        self._replace_output_text(new_text)
        self._sync_research_text()

    def _clear_output_text(self) -> None:
        self._replace_output_text(
            self.session_service.clear_output_text(
                self.project,
                self.current_scene,
                self.current_scene_index,
                self.current_mode,
            )
        )
        self._sync_research_text()

    def configure_text_style(self) -> None:
        if self.current_mode != "design":
            return

        def on_save(size: int, bold: bool, uppercase: bool, visible: bool) -> None:
            self.controller.update_text_style(size, bold, uppercase, visible)
            self._refresh_all()

        TextStyleDialog(
            self.root,
            self.project.cell_text_size,
            self.project.cell_text_bold,
            self.project.cell_text_uppercase,
            self.project.cell_text_visible,
            on_save,
        )

    # ------------------------------
    # Project actions
    # ------------------------------
    def _reset_research_after_project_change(self, reason: str) -> None:
        self.project_workflow.reset_research_after_project_change(
            self.current_mode,
            self._sync_research_context,
            reason,
        )

    def new_project(self) -> None:
        # Full runtime reset before creating a new project. This prevents stale
        # support images/text/visibility from a previous project.
        self._reset_transient_project_ui_state(hide_supports=True)
        self.project_workflow.new_project(
            default_project_name(),
            current_mode=self.current_mode,
            sync_context=self._sync_research_context,
            reason="new_project",
        )
        try:
            normalize_supports(self.current_scene)
        except Exception:
            pass
        self._reset_transient_project_ui_state(hide_supports=True)
        self._refresh_all()

    def open_project(self) -> None:
        path = self._ask_open_filename(initialdir=self._open_project_initial_dir(), filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        # Clear old project caches first, then render only the loaded project.
        self._reset_transient_project_ui_state(hide_supports=True)
        self.project_workflow.open_project(
            path,
            current_mode=self.current_mode,
            sync_context=self._sync_research_context,
            reason="load_project",
        )
        try:
            normalize_supports(self.current_scene)
        except Exception:
            pass
        self._clear_support_widget_cache()
        self._set_support_strip_from_current_scene()
        self._replace_output_text("")
        self._refresh_all()

    def save_project(self) -> None:
        if not self.project.file_path:
            self.save_project_as()
            return
        self.project_workflow.save_project(current_mode=self.current_mode)
        self._refresh_all()
        self.dialogs.info(tr("msg_project_saved_title"), tr("msg_project_saved"), parent=self.root)

    def save_project_as(self) -> None:
        path = self._ask_save_filename(
            initialdir=str(config.PROJECTS_DIR),
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        self.project_workflow.save_project(current_mode=self.current_mode, path=path)
        self._refresh_all()
        self.dialogs.info(tr("msg_project_saved_title"), tr("msg_project_saved"), parent=self.root)

    def configure_grid(self) -> None:
        if self.current_mode != "design":
            return

        def on_save(rows: int, cols: int) -> None:
            self.scene_workflow.configure_grid(rows, cols)
            self._refresh_all()

        GridSettingsDialog(self.root, self.project.grid_rows, self.project.grid_cols, on_save)

    # ------------------------------
    # Scene actions
    # ------------------------------
    def add_scene(self) -> None:
        self.scene_workflow.add_scene()
        self._sync_support_strip_for_scene_navigation()
        self._refresh_all()

    def duplicate_scene(self) -> None:
        self.scene_workflow.duplicate_scene()
        self._sync_support_strip_for_scene_navigation()
        self._refresh_all()

    def delete_scene(self) -> None:
        self.delete_scene_at(self.current_scene_index)

    def duplicate_scene_at(self, index: int) -> None:
        if index < 0 or index >= len(self.project.scenes):
            return
        self.scene_workflow.go_to_scene(index)
        self._sync_support_strip_for_scene_navigation()
        self.scene_workflow.duplicate_scene()
        self._sync_support_strip_for_scene_navigation()
        self._refresh_all()

    def delete_scene_at(self, index: int) -> None:
        if index < 0 or index >= len(self.project.scenes):
            return
        can_delete, payload = self.scene_workflow.can_delete_scene(index)
        if not can_delete:
            self.dialogs.info(tr("scene_panel_title"), payload, parent=self.root)
            return
        if not self.dialogs.confirm_yes_no(tr("msg_delete_scene_title"), tr("msg_panel_delete_scene", title=payload), parent=self.root):
            return
        self.scene_workflow.go_to_scene(index)
        self._sync_support_strip_for_scene_navigation()
        self.scene_workflow.delete_current_scene()
        self._sync_support_strip_for_scene_navigation()
        self._refresh_all()

    def rename_scene_at(self, index: int) -> None:
        if index < 0 or index >= len(self.project.scenes):
            return
        current_title = str(getattr(self.project.scenes[index], "title", "") or "")
        new_title = simpledialog.askstring(tr("rename_scene"), tr("scene_name_prompt"), initialvalue=current_title, parent=self.root)
        if new_title is None:
            return
        self.scene_workflow.rename_scene(index, new_title)
        self._refresh_all()

    def move_scene_at(self, from_index: int, to_index: int) -> None:
        if from_index < 0 or from_index >= len(self.project.scenes):
            return
        if to_index < 0 or to_index >= len(self.project.scenes):
            return
        self.scene_workflow.move_scene(from_index, to_index)
        self._refresh_all()

    def edit_scene_at(self, index: int) -> None:
        if index < 0 or index >= len(self.project.scenes):
            return
        self.scene_workflow.go_to_scene(index)
        self._sync_support_strip_for_scene_navigation()
        self._refresh_all()
        self.edit_scene()

    def previous_scene(self) -> None:
        self._clear_last_hotspot_event()
        self.scene_workflow.previous_scene()
        self._sync_support_strip_for_scene_navigation()
        self._refresh_all()

    def next_scene(self) -> None:
        self._clear_last_hotspot_event()
        self.scene_workflow.next_scene()
        self._sync_support_strip_for_scene_navigation()
        self._refresh_all()

    def edit_scene(self) -> None:
        if self.current_mode != "design":
            return

        def on_save(scene: Scene) -> None:
            self.scene_workflow.update_scene(scene)
            self._refresh_all()
            self._refresh_scene_audio_button_visibility()

        SceneEditorDialog(self.root, self.current_scene, on_save)

    def play_scene_audio(self) -> None:
        self.session_service.play_scene_audio(
            self.project,
            self.current_scene,
            self.current_scene_index,
            self.current_mode,
        )

    def open_storyboard(self) -> None:
        def on_go(index: int) -> None:
            self.scene_workflow.go_to_scene(index)
            self._sync_support_strip_for_scene_navigation()
            self._refresh_all()

        def on_move(from_index: int, to_index: int) -> None:
            self.scene_workflow.move_scene(from_index, to_index)
            self._refresh_all()

        def on_rename(index: int, title: str) -> None:
            self.scene_workflow.rename_scene(index, title)
            self._refresh_all()

        def on_delete(index: int) -> None:
            can_delete, payload = self.scene_workflow.can_delete_scene(index)
            if not can_delete:
                self.dialogs.info(tr("scene_panel_title"), payload, parent=self.root)
                return
            if not self.dialogs.confirm_yes_no(tr('scene_panel_title'), tr('msg_panel_delete_scene', title=payload), parent=self.root):
                return
            self.scene_workflow.go_to_scene(index)
            self._sync_support_strip_for_scene_navigation()
            self.scene_workflow.delete_current_scene()
            self._sync_support_strip_for_scene_navigation()
            self._refresh_all()

        StoryboardDialog(self.root, self.project, self.current_scene_index, on_go, on_move, on_rename, on_delete)

    # ------------------------------
    # Cell actions
    # ------------------------------
    def activate_cell(self, index: int) -> None:
        current = ""
        result = self.cell_workflow.activate_cell(
            self.project,
            self.current_scene,
            self.current_scene_index,
            self.current_mode,
            index,
            current,
        )
        if result.action == "ignored":
            return
        if result.action == "edit":
            self.edit_cell(index)
            return

        if result.inserted_text:
            # SaraB support activations do not accumulate into a visible message.
            self._replace_output_text("")
            self._sync_research_text()

    def edit_cell(self, index: int) -> None:
        if not self.cell_workflow.can_edit_cell(self.project, self.current_mode, index):
            return
        cell = self.cell_workflow.get_cell_for_edit(self.current_scene, index)

        def _handle_save(updated) -> None:
            self.cell_workflow.apply_cell_update(
                index,
                updated,
                on_save=lambda _saved: self._refresh_all(),
            )

        CellEditorDialog(
            self.root,
            cell,
            _handle_save,
            scene_id=str(getattr(self.current_scene, "id", "") or ""),
            project_path=str(getattr(self.project, "file_path", "") or ""),
        )

    def activate_support(self, index: int) -> None:
        current = ""
        result = self.session_service.activate_support(
            self.project,
            self.current_scene,
            self.current_scene_index,
            self.current_mode,
            index,
            current,
        )
        if result.action == "ignored":
            return
        if result.action == "edit":
            self.edit_support(index)
            return
        if result.inserted_text:
            # SaraB supports do not accumulate into a visible message.
            self._replace_output_text("")
            self._sync_research_text()

    def edit_support(self, index: int) -> None:
        if self.current_mode != "design":
            return
        supports = list(getattr(self.current_scene, "supports", []) or [])
        if not (0 <= int(index) < len(supports)):
            return
        support = supports[int(index)]

        def _handle_save(updated) -> None:
            updated.position = int(index)
            updated.id = f"support_{int(index) + 1}"
            updated.cell_type = "visual_support"
            # If the clinician adds text, image, or audio, the support becomes
            # visible automatically. The clinician can still hide it later by
            # unchecking Visible. If it remains empty, preserve the checkbox
            # state that may already have been chosen before editing.
            has_content = self._support_has_content(updated)
            previous_visible = bool(getattr(support, "visible", False))
            updated.visible = True if has_content else previous_visible
            self.controller.update_support(int(index), updated)
            if 0 <= int(index) < len(self.support_visible_vars):
                try:
                    self.support_visible_vars[int(index)].set(bool(updated.visible))
                except Exception:
                    pass
            self._refresh_all()

        CellEditorDialog(
            self.root,
            support,
            _handle_save,
            scene_id=str(getattr(self.current_scene, "id", "") or ""),
            project_path=str(getattr(self.project, "file_path", "") or ""),
        )

    # ------------------------------
    # Modes and research
    # ------------------------------
    def set_mode(self, mode: str) -> None:
        self.controller.set_mode(mode)
        if mode != "design":
            self._clear_hotspot_label_timer()
            self.hotspot_edit_mode = False
            self.hotspot_edit_enabled_var.set(False)
            self.hotspot_drag_start = None
            self.hotspot_drag_state = None
            self.hotspot_preview_rect = None
            self.selected_hotspot_id = ""
        self.hotspot_drag_state = None
        self._build_menu()
        self._sync_research_context()
        self._refresh_all()

    def _ensure_research_participant_policy(self) -> bool:
        return bool(self.research_workflow.ensure_participant_policy(self.root, self.select_user))

    def toggle_research(self) -> None:
        if getattr(self, "current_mode", "design") == "user":
            # Safety policy: research can only be changed from Design/Therapist mode.
            return
        result = self.research_workflow.toggle_research(
            self.root,
            self.research.research_enabled,
            self.users_manager.current_user_id or "",
            self.users_manager.get_current_user_name() or "",
            self.select_user,
        )
        if result is None:
            return
        if result is False:
            self._clear_last_hotspot_event()
        self._sync_research_context()
        self._refresh_all()

    def select_user(self) -> None:
        def on_select(user_id: str) -> None:
            self.users_manager.current_user_id = user_id
            try:
                self.research.set_participant_context(session_type="participant", is_anonymous=False)
            except Exception:
                pass
            self._refresh_all()

        dlg = UserSelectionDialog(self.root, self.users_manager, on_select)
        try:
            self.root.wait_window(dlg)
        except Exception:
            pass

    def force_session_summary(self) -> None:
        result = self.research_workflow.force_session_summary()
        if isinstance(result, dict):
            self.dialogs.info(result.get("title", tr("research")), result.get("message", ""), parent=self.root)

    def show_session_stats(self) -> None:
        scene_order = [
            {
                "id": str(getattr(scene, "id", "") or ""),
                "title": str(getattr(scene, "title", "") or f"Scene {idx + 1}"),
                "scene_focus_category_id": str(getattr(scene, "scene_focus_category_id", "") or ""),
                "scene_focus_category_label": str(getattr(scene, "scene_focus_category_label", "") or ""),
                "scene_specific_topic": str(getattr(scene, "scene_specific_topic", "") or ""),
            }
            for idx, scene in enumerate(list(getattr(self.project, "scenes", []) or []))
        ]
        payload = self.research_workflow.build_session_stats_payload(
            project_name=self.project.project_name,
            current_scene_index=self.current_scene_index,
            total_scenes=len(self.project.scenes),
            rows=self.project.grid_rows,
            cols=self.project.grid_cols,
            mode=self._research_mode_name(),
            scene_order=scene_order,
        )
        last_event = getattr(self, "_last_response_event", None) or getattr(self, "_last_hotspot_event", None) or {}
        payload["last_hotspot_label"] = last_event.get("response_label", "") or last_event.get("hotspot_label", "")
        payload["last_response_mark"] = last_event.get("response_mark", getattr(self, "_last_response_mark", "unmarked"))
        show_session_stats_dialog(self.root, **payload)

    def _research_identity_for_display(self) -> tuple[str, str]:
        return self.research_workflow.identity_for_display()

    def show_research_diagnostics(self) -> None:
        snapshot = self.research_workflow.build_research_diagnostics_snapshot()
        show_research_diagnostics_dialog(self.root, snapshot)

    # ------------------------------
    # Misc
    # ------------------------------
    def show_about(self) -> None:
        from app.ui_dialogs import show_about_dialog
        msg = tr("about_message", app_name=config.APP_TITLE, version=getattr(config, "APP_DISPLAY_VERSION", config.APP_VERSION), author=config.AUTHOR, license_line=getattr(config, "LICENSE_LINE", "—"), cite_line=getattr(config, "CITE_LINE", "—"), subtitle=config.APP_SUBTITLE)
        show_about_dialog(self.root, tr("about_title"), msg)

    def _layout_name(self) -> str:
        return self.session_service.layout_name(self.project)

    def _research_mode_name(self) -> str:
        return self.session_service.research_mode_name(self.current_mode)

    def set_language(self, lang: str) -> None:
        set_language(lang)
        try:
            from app.services.settings_service import SettingsService
            SettingsService.set_ui_language(lang)
        except Exception:
            pass
        self.research.set_ui_language(getattr(config, "CURRENT_UI_LANGUAGE", getattr(config, "DEFAULT_UI_LANGUAGE", "es")))
        self.controller.relocalize_default_project_name()
        self.controller.relocalize_default_scene_titles()
        self._build_menu()
        if hasattr(self, "thumbnail_toggle"):
            self.thumbnail_toggle.configure(text=tr("navigation_bar_toggle"))
        if hasattr(self, "support_toggle"):
            self.support_toggle.configure(text=tr("supports_toggle"))
        if hasattr(self, "hotspot_overlay_toggle"):
            self.hotspot_overlay_toggle.configure(text=tr("show_hotspots_toggle"))
        self.scene_controls.apply_language()
        self._refresh_action_buttons()
        self._refresh_toolbar_mode_button()
        self._refresh_all()

    def on_close(self) -> None:
        self.lifecycle_service.close(self.root)
