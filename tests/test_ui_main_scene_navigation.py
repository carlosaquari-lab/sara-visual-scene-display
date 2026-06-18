import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.ui_main as ui_main
from app.controller import AppController
from app.models import Scene, StoryProject
from app.services.scene_workflow_service import SceneWorkflowService
from app.ui_main import SaraApp


class NavigationSpies:
    def __init__(self):
        self.sync_calls = 0
        self.refresh_calls = 0

    def install(self, app) -> None:
        app._sync_support_strip_for_scene_navigation = self.sync
        app._refresh_all = self.refresh

    def sync(self) -> None:
        self.sync_calls += 1

    def refresh(self) -> None:
        self.refresh_calls += 1


class FakeDialogs:
    def __init__(self, confirm: bool = True):
        self.confirm = confirm
        self.info_calls = 0
        self.confirm_calls = 0

    def info(self, *args, **kwargs) -> None:
        self.info_calls += 1

    def confirm_yes_no(self, *args, **kwargs) -> bool:
        self.confirm_calls += 1
        return self.confirm


def _scene(index: int, title: str | None = None) -> Scene:
    return Scene(id=f"scene_{index}", title=title or f"Scene {index}")


def _project(scene_count: int = 3) -> StoryProject:
    return StoryProject(
        project_name="Scene Navigation",
        scenes=[_scene(index) for index in range(1, scene_count + 1)],
    )


def _app(project: StoryProject | None = None, current_scene_index: int = 0):
    app = object.__new__(SaraApp)
    app.controller = AppController()
    app.controller.project = project or _project()
    app.controller.current_scene_index = current_scene_index
    app.scene_workflow = SceneWorkflowService(app.controller)
    app.dialogs = FakeDialogs()
    app.root = None
    spies = NavigationSpies()
    spies.install(app)
    return app, spies


def test_handle_scene_change_valid_index_updates_scene_and_syncs_refreshes():
    app, spies = _app(current_scene_index=0)

    app._handle_scene_change(2)

    assert app.current_scene_index == 2
    assert app.current_scene.id == "scene_3"
    assert spies.sync_calls == 1
    assert spies.refresh_calls == 1


def test_handle_scene_change_current_index_does_not_refresh():
    app, spies = _app(current_scene_index=1)

    app._handle_scene_change(1)

    assert app.current_scene_index == 1
    assert spies.sync_calls == 0
    assert spies.refresh_calls == 0


def test_previous_scene_moves_to_previous_scene_and_syncs_refreshes():
    app, spies = _app(current_scene_index=2)

    app.previous_scene()

    assert app.current_scene_index == 1
    assert app.current_scene.id == "scene_2"
    assert spies.sync_calls == 1
    assert spies.refresh_calls == 1


def test_next_scene_moves_to_next_scene_and_syncs_refreshes():
    app, spies = _app(current_scene_index=0)

    app.next_scene()

    assert app.current_scene_index == 1
    assert app.current_scene.id == "scene_2"
    assert spies.sync_calls == 1
    assert spies.refresh_calls == 1


def test_add_scene_creates_and_selects_new_scene_then_syncs_refreshes():
    app, spies = _app(project=_project(scene_count=2), current_scene_index=0)

    app.add_scene()

    assert len(app.project.scenes) == 3
    assert app.current_scene_index == 2
    assert app.current_scene.id == "scene_3"
    assert spies.sync_calls == 1
    assert spies.refresh_calls == 1


def test_duplicate_scene_duplicates_current_scene_selects_copy_then_syncs_refreshes():
    app, spies = _app(current_scene_index=1)
    source = app.current_scene

    app.duplicate_scene()

    assert len(app.project.scenes) == 4
    assert app.current_scene_index == 2
    assert app.current_scene is not source
    assert app.current_scene.id == "scene_4"
    assert spies.sync_calls == 1
    assert spies.refresh_calls == 1


def test_move_scene_at_moves_scenes_and_refreshes_without_support_sync():
    app, spies = _app(current_scene_index=0)

    app.move_scene_at(0, 2)

    assert [scene.id for scene in app.project.scenes] == ["scene_2", "scene_3", "scene_1"]
    assert app.current_scene_index == 2
    assert app.current_scene.id == "scene_1"
    assert spies.sync_calls == 0
    assert spies.refresh_calls == 1


def test_delete_scene_at_with_confirmation_deletes_scene_and_syncs_refreshes():
    app, spies = _app(current_scene_index=0)
    app.dialogs = FakeDialogs(confirm=True)

    app.delete_scene_at(1)

    assert [scene.id for scene in app.project.scenes] == ["scene_1", "scene_3"]
    assert app.current_scene_index == 1
    assert app.current_scene.id == "scene_3"
    assert app.dialogs.confirm_calls == 1
    assert spies.sync_calls == 2
    assert spies.refresh_calls == 1


def test_delete_scene_at_with_negative_confirmation_does_not_delete_or_refresh():
    app, spies = _app(current_scene_index=0)
    app.dialogs = FakeDialogs(confirm=False)

    app.delete_scene_at(1)

    assert [scene.id for scene in app.project.scenes] == ["scene_1", "scene_2", "scene_3"]
    assert app.current_scene_index == 0
    assert app.dialogs.confirm_calls == 1
    assert spies.sync_calls == 0
    assert spies.refresh_calls == 0


def test_delete_scene_at_does_not_leave_current_scene_index_out_of_range():
    app, spies = _app(current_scene_index=0)
    app.dialogs = FakeDialogs(confirm=True)

    app.delete_scene_at(2)

    assert len(app.project.scenes) == 2
    assert 0 <= app.current_scene_index < len(app.project.scenes)
    assert app.current_scene_index == 1
    assert app.current_scene.id == "scene_2"
    assert spies.sync_calls == 2
    assert spies.refresh_calls == 1


def test_rename_scene_at_with_new_name_updates_title_and_refreshes(monkeypatch):
    app, spies = _app(current_scene_index=0)
    monkeypatch.setattr(ui_main.simpledialog, "askstring", lambda *args, **kwargs: "New title")

    app.rename_scene_at(1)

    assert app.project.scenes[1].title == "New title"
    assert spies.sync_calls == 0
    assert spies.refresh_calls == 1


def test_rename_scene_at_cancel_does_not_change_title_or_refresh(monkeypatch):
    app, spies = _app(current_scene_index=0)
    original_title = app.project.scenes[1].title
    monkeypatch.setattr(ui_main.simpledialog, "askstring", lambda *args, **kwargs: None)

    app.rename_scene_at(1)

    assert app.project.scenes[1].title == original_title
    assert spies.sync_calls == 0
    assert spies.refresh_calls == 0


def test_rename_scene_at_empty_text_uses_current_fallback_title_and_refreshes(monkeypatch):
    app, spies = _app(current_scene_index=0)
    app.project.scenes[1].title = "Original title"
    monkeypatch.setattr(ui_main.simpledialog, "askstring", lambda *args, **kwargs: "")

    app.rename_scene_at(1)

    assert app.project.scenes[1].title
    assert app.project.scenes[1].title != "Original title"
    assert spies.sync_calls == 0
    assert spies.refresh_calls == 1
