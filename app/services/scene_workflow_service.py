from __future__ import annotations

from app.i18n import localize_scene_title, tr


class SceneWorkflowService:
    """Encapsulate scene navigation and storyboard operations."""

    def __init__(self, controller):
        self.controller = controller

    @property
    def project(self):
        return self.controller.project

    def apply_grid_label(self, value: str) -> bool:
        return self.controller.apply_grid_label(value)

    def configure_grid(self, rows: int, cols: int) -> None:
        self.controller.apply_grid(rows, cols)

    def add_scene(self):
        return self.controller.add_scene()

    def duplicate_scene(self):
        return self.controller.duplicate_scene()

    def delete_current_scene(self):
        return self.controller.delete_scene()

    def previous_scene(self):
        return self.controller.previous_scene()

    def next_scene(self):
        return self.controller.next_scene()

    def update_scene(self, scene):
        return self.controller.update_scene(scene)

    def go_to_scene(self, index: int):
        return self.controller.go_to_scene(index)

    def move_scene(self, from_index: int, to_index: int):
        return self.controller.move_scene(from_index, to_index)

    def rename_scene(self, index: int, title: str):
        return self.controller.rename_scene(index, title)

    def can_delete_scene(self, index: int) -> tuple[bool, str]:
        if len(self.project.scenes) <= 1:
            return False, tr("msg_panel_keep_one")
        title = localize_scene_title(self.project.scenes[index].title, index + 1)
        return True, title
