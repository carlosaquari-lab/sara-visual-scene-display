import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.controller import AppController
from app.models import HotspotData, Scene, StoryProject
from app.ui_main import SaraApp


class FakeSessionService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def activate_hotspot(self, project, current_scene, current_scene_index, current_mode, hotspot, current_text):
        self.calls.append(
            {
                "project": project,
                "current_scene": current_scene,
                "current_scene_index": current_scene_index,
                "current_mode": current_mode,
                "hotspot": hotspot,
                "current_text": current_text,
            }
        )
        return self.result


class HotspotActivationSpies:
    def __init__(self):
        self.schedule_calls = []
        self.clear_timer_calls = 0
        self.render_calls = 0
        self.refresh_calls = 0
        self.sync_support_calls = 0
        self.sync_research_text_calls = 0

    def install(self, app) -> None:
        app._schedule_hotspot_label_hide = self.schedule
        app._clear_hotspot_label_timer = self.clear_timer
        app._render_scene_image = self.render
        app._refresh_all = self.refresh
        app._sync_support_strip_for_scene_navigation = self.sync_support
        app._sync_research_text = self.sync_research_text

    def schedule(self, hotspot) -> None:
        self.schedule_calls.append(hotspot)

    def clear_timer(self) -> None:
        self.clear_timer_calls += 1

    def render(self) -> None:
        self.render_calls += 1

    def refresh(self) -> None:
        self.refresh_calls += 1

    def sync_support(self) -> None:
        self.sync_support_calls += 1

    def sync_research_text(self) -> None:
        self.sync_research_text_calls += 1


def _hotspot(hotspot_id: str = "h1") -> HotspotData:
    return HotspotData(id=hotspot_id, label="Help", text="help")


def _result(action: str = "insert", target_scene_id: str = ""):
    return SimpleNamespace(action=action, target_scene_id=target_scene_id)


def _app(result, current_scene_index: int = 0):
    scenes = [
        Scene(id="scene_1", title="Scene 1"),
        Scene(id="scene_2", title="Scene 2"),
    ]
    project = StoryProject(project_name="Hotspot Activation", scenes=scenes)
    app = object.__new__(SaraApp)
    app.controller = AppController()
    app.controller.project = project
    app.controller.current_scene_index = current_scene_index
    app.current_mode = "user"
    app.output_buffer = "previous text"
    app.selected_hotspot_id = ""
    app.session_service = FakeSessionService(result)
    spies = HotspotActivationSpies()
    spies.install(app)
    return app, spies


def test_activate_hotspot_ignored_result_selects_schedules_and_renders_only():
    hotspot = _hotspot()
    app, spies = _app(_result(action="ignored"))

    app.activate_hotspot(hotspot)

    assert app.selected_hotspot_id == "h1"
    assert spies.schedule_calls == [hotspot]
    assert len(app.session_service.calls) == 1
    assert app.session_service.calls[0]["hotspot"] is hotspot
    assert app.session_service.calls[0]["current_text"] == ""
    assert spies.render_calls == 1
    assert spies.refresh_calls == 0
    assert spies.sync_support_calls == 0
    assert spies.clear_timer_calls == 0


def test_activate_hotspot_insert_without_target_clears_output_syncs_text_and_renders():
    hotspot = _hotspot()
    app, spies = _app(_result(action="insert"))

    app.activate_hotspot(hotspot)

    assert app.selected_hotspot_id == "h1"
    assert app.output_buffer == ""
    assert spies.schedule_calls == [hotspot]
    assert spies.sync_research_text_calls == 1
    assert spies.render_calls == 1
    assert spies.refresh_calls == 0
    assert spies.sync_support_calls == 0
    assert spies.clear_timer_calls == 0


def test_activate_hotspot_insert_with_different_valid_target_changes_scene_and_refreshes():
    hotspot = _hotspot()
    app, spies = _app(_result(action="insert", target_scene_id="scene_2"), current_scene_index=0)

    app.activate_hotspot(hotspot)

    assert app.current_scene_index == 1
    assert app.current_scene.id == "scene_2"
    assert app.selected_hotspot_id == ""
    assert app.output_buffer == ""
    assert spies.schedule_calls == [hotspot]
    assert spies.sync_research_text_calls == 1
    assert spies.sync_support_calls == 1
    assert spies.clear_timer_calls == 1
    assert spies.refresh_calls == 1
    assert spies.render_calls == 0


def test_activate_hotspot_insert_with_current_scene_target_renders_without_refreshing():
    hotspot = _hotspot()
    app, spies = _app(_result(action="insert", target_scene_id="scene_1"), current_scene_index=0)

    app.activate_hotspot(hotspot)

    assert app.current_scene_index == 0
    assert app.selected_hotspot_id == "h1"
    assert spies.sync_research_text_calls == 1
    assert spies.render_calls == 1
    assert spies.refresh_calls == 0
    assert spies.sync_support_calls == 0
    assert spies.clear_timer_calls == 0


def test_activate_hotspot_insert_with_missing_target_renders_without_changing_scene():
    hotspot = _hotspot()
    app, spies = _app(_result(action="insert", target_scene_id="missing"), current_scene_index=0)

    app.activate_hotspot(hotspot)

    assert app.current_scene_index == 0
    assert app.selected_hotspot_id == "h1"
    assert spies.sync_research_text_calls == 1
    assert spies.render_calls == 1
    assert spies.refresh_calls == 0
    assert spies.sync_support_calls == 0
    assert spies.clear_timer_calls == 0
