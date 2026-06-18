from __future__ import annotations

import os
from typing import Callable

from app import config


class ProjectWorkflowService:
    """Handle project lifecycle actions outside ui_main."""

    def __init__(self, controller, research, session_service):
        self.controller = controller
        self.research = research
        self.session_service = session_service

    def research_mode_name(self, current_mode: str) -> str:
        return "User" if current_mode == "user" else "Therapist"

    def reset_research_after_project_change(self, current_mode: str, sync_context: Callable[[], None], reason: str) -> None:
        try:
            self.research.set_current_text("", mode="Therapist")
            if self.research.research_enabled:
                # If the current research session already contains participant
                # activity, close it before the project changes. If it only
                # contains a pending ON/audit state, do not create empty logs.
                self.research.start_new_session(
                    reason=reason,
                    write_previous=bool(self.research.has_activity()),
                )
            else:
                self.research.reset_session(new_mode=self.research_mode_name(current_mode))
            sync_context()
        except Exception:
            pass

    def new_project(self, name: str, *, current_mode: str, sync_context: Callable[[], None], reason: str = "new_project"):
        project = self.controller.create_new_project(name)
        self.reset_research_after_project_change(current_mode, sync_context, reason)
        return project

    def open_project(self, path: str, *, current_mode: str, sync_context: Callable[[], None], reason: str = "load_project"):
        project = self.controller.open_project(path)
        self.reset_research_after_project_change(current_mode, sync_context, reason)
        self.research.log_event(
            action="layout_load",
            layout_file=os.path.basename(path),
            mode=self.research_mode_name(current_mode),
            project_title=project.project_name,
            scene_id=str(self.controller.current_scene.id),
            scene_title=self.controller.current_scene.title,
            scene_index=self.controller.current_scene_index,
        )
        return project

    def save_project(self, *, current_mode: str, path: str | None = None) -> str:
        saved_path = self.controller.save_project(path)
        self.session_service.log_layout_save(
            self.controller.project,
            self.controller.current_scene,
            self.controller.current_scene_index,
            current_mode,
            layout_file=os.path.basename(saved_path),
        )
        return saved_path
