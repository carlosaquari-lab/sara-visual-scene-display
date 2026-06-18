import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.controller import AppController
from app.models import HotspotData, Scene, StoryProject
from app.ui_main import SaraApp


class FakeEvent:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y


class RenderCursorSpies:
    def __init__(self):
        self.render_calls = 0
        self.cursor_calls = 0

    def install(self, app) -> None:
        app._render_scene_image = self.render
        app._update_scene_cursor = self.cursor

    def render(self) -> None:
        self.render_calls += 1

    def cursor(self, *args, **kwargs) -> None:
        self.cursor_calls += 1


def _hotspot(hotspot_id: str, x: float = 0.1, y: float = 0.2) -> HotspotData:
    return HotspotData(
        id=hotspot_id,
        label=hotspot_id,
        x=x,
        y=y,
        width=0.2,
        height=0.2,
    )


def _app(hotspots: list[HotspotData] | None = None):
    scene = Scene(id="scene_1", title="Scene 1", hotspots=list(hotspots or []))
    project = StoryProject(project_name="Hotspot State", scenes=[scene])
    app = object.__new__(SaraApp)
    app.controller = AppController()
    app.controller.project = project
    app.controller.current_scene_index = 0
    app.scene_render_info = {
        "image_x": 20,
        "image_y": 30,
        "display_width": 200,
        "display_height": 100,
    }
    app.selected_hotspot_id = ""
    spies = RenderCursorSpies()
    spies.install(app)
    return app, spies


def test_event_to_local_scene_xy_converts_event_coordinates_using_image_offset():
    app, _spies = _app()

    local = app._event_to_local_scene_xy(FakeEvent(70, 80))

    assert local == (50, 50, 200, 100)


def test_event_to_local_scene_xy_clamps_coordinates_inside_image_bounds():
    app, _spies = _app()

    assert app._event_to_local_scene_xy(FakeEvent(-100, -100)) == (0, 0, 200, 100)
    assert app._event_to_local_scene_xy(FakeEvent(999, 999)) == (200, 100, 200, 100)


def test_event_to_hotspot_rect_returns_normalized_rect_for_large_drag():
    app, _spies = _app()

    rect = app._event_to_hotspot_rect(FakeEvent(40, 50), FakeEvent(140, 90))

    assert rect == {
        "x": 0.1,
        "y": 0.2,
        "width": 0.5,
        "height": 0.4,
    }


def test_event_to_hotspot_rect_returns_none_for_too_small_drag():
    app, _spies = _app()

    assert app._event_to_hotspot_rect(FakeEvent(40, 50), FakeEvent(50, 60)) is None


def test_current_selected_hotspot_returns_hotspot_by_id():
    first = _hotspot("h1")
    second = _hotspot("h2")
    app, _spies = _app([first, second])
    app.selected_hotspot_id = "h2"

    assert app._current_selected_hotspot() is second


def test_current_selected_hotspot_returns_none_for_missing_id():
    app, _spies = _app([_hotspot("h1")])
    app.selected_hotspot_id = "missing"

    assert app._current_selected_hotspot() is None


def test_delete_hotspot_removes_selected_hotspot_clears_selection_and_refreshes():
    first = _hotspot("h1")
    second = _hotspot("h2")
    app, spies = _app([first, second])
    app.selected_hotspot_id = "h2"
    app.hotspot_drag_state = {"mode": "move"}
    app.hotspot_preview_rect = {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}

    app._delete_hotspot(second)

    assert app.current_scene.hotspots == [first]
    assert app.selected_hotspot_id == ""
    assert app.hotspot_drag_state is None
    assert app.hotspot_preview_rect is None
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1
