from __future__ import annotations

from app.models import CellData
from app.ui_dialogs import CellEditorDialog


class CellWorkflowService:
    """Encapsulate cell activation and edition workflows."""

    def __init__(self, controller, session_service):
        self.controller = controller
        self.session_service = session_service

    def activate_cell(self, project, current_scene, current_scene_index: int, current_mode: str, index: int, current_text: str):
        return self.session_service.activate_cell(
            project,
            current_scene,
            current_scene_index,
            current_mode,
            index,
            current_text,
        )

    def can_edit_cell(self, project, current_mode: str, index: int) -> bool:
        try:
            return current_mode == "design" and 0 <= int(index) < int(project.total_cells)
        except Exception:
            return False

    def get_cell_for_edit(self, current_scene, index: int) -> CellData:
        return current_scene.cells[int(index)]

    def apply_cell_update(self, index: int, updated: CellData, on_save=None) -> CellData:
        saved = self.controller.update_cell(int(index), updated)
        if on_save:
            on_save(saved)
        return saved

    def open_cell_editor(self, parent, project, current_scene, current_mode: str, index: int, on_save) -> bool:
        if not self.can_edit_cell(project, current_mode, index):
            return False
        cell = self.get_cell_for_edit(current_scene, index)

        def _handle_save(updated: CellData) -> None:
            self.apply_cell_update(index, updated, on_save=on_save)

        CellEditorDialog(parent, cell, _handle_save)
        return True
