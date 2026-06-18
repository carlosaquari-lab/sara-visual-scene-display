from __future__ import annotations

from app import config
import tkinter as tk


class UIStateService:
    """Keeps view state updates out of the main tkinter window class."""

    def __init__(self, controller):
        self.controller = controller

    def build_header_state(self, users_manager, research) -> dict:
        status = self.controller.project_status(
            current_user=users_manager.get_current_user_name() or "—",
            research_enabled=research.research_enabled,
        )
        return {
            "project": status["project"],
            "scene_title": "",
            "scene": status["scene"],
            "mode": status["mode"],
            "grid": status["grid"],
            "user": status["user"],
            "research": status["research"],
        }

    def refresh_scene_controls(self, scene_controls, project, current_scene_index: int, current_mode: str) -> None:
        scene_controls.set_scene_values(self.controller.scene_selector_values(), current_scene_index)
        scene_controls.set_grid_value(f"{project.grid_rows}x{project.grid_cols}")
        # Lower scene selector/options are hidden in Sara 0.1.15.
        scene_controls.set_visible(False)
        scene_controls.set_design_mode(False)

    def _set_widget_enabled(self, widget, enabled: bool) -> None:
        """Support both ttk widgets (.state) and classic tk widgets (.configure)."""
        if widget is None:
            return
        try:
            if hasattr(widget, "state"):
                widget.state(["!disabled"] if enabled else ["disabled"])
            else:
                widget.configure(state=(tk.NORMAL if enabled else tk.DISABLED))
        except Exception:
            try:
                widget.configure(state=(tk.NORMAL if enabled else tk.DISABLED))
            except Exception:
                pass
        # Optional visual feedback for tk.Button widgets used in Sara.
        if not hasattr(widget, "state"):
            try:
                widget.configure(cursor=("hand2" if enabled else "arrow"))
            except Exception:
                pass

    def update_navigation_buttons(self, prev_button, next_button, current_scene_index: int, total_scenes: int) -> None:
        has_previous = current_scene_index > 0
        self._set_widget_enabled(prev_button, has_previous)
        has_next = current_scene_index < max(total_scenes - 1, 0)
        self._set_widget_enabled(next_button, has_next)

    def resize_main_panel(
        self,
        main,
        left_panel,
        right_panel,
        scene_controls,
        thumbnail_bar,
        scene_image_frame,
        render_scene_image,
        render_scene_thumbnails,
        thumbnail_bar_visible: bool = True,
        support_bar=None,
        support_bar_visible: bool = False,
        render_support_strip=None,
    ) -> None:
        total_w = max(main.winfo_width(), 900)
        total_h = max(main.winfo_height(), 520)

        # SaraB: image-centred layout. The scene remains dominant. Optional
        # visual supports occupy a narrow right column only when enabled.
        support_w = 196 if support_bar_visible else 0
        gap_w = 16 if support_bar_visible else 0
        left_w = max(740, min(1120, total_w - support_w - gap_w - 40))
        image_h = max(360, total_h - 8)
        strip_h = 108

        left_panel.configure(width=left_w, height=image_h + 4)
        try:
            right_panel.configure(width=1)
            right_panel.grid_remove()
        except Exception:
            pass
        if thumbnail_bar_visible:
            thumbnail_bar.configure(width=max(left_w, 720), height=strip_h)
            render_scene_thumbnails()
        if support_bar is not None and support_bar_visible:
            try:
                support_bar.configure(width=support_w, height=image_h + 4)
            except Exception:
                pass
            if callable(render_support_strip):
                render_support_strip()
        scene_image_frame.configure(width=left_w, height=image_h)
        render_scene_image()
