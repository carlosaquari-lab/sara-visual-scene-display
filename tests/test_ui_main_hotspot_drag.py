import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.controller import AppController
from app.models import HotspotData, Scene, StoryProject
from app.services.scene_image_view_service import SceneImageViewService
from app.ui_main import SaraApp


class FakeEvent:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y


class FakeSceneImageView:
    def __init__(self, hotspot=None, handle=None):
        self.hotspot = hotspot
        self.handle = handle

    def hotspot_hit_test(self, hotspots, render_info, x, y):
        return self.hotspot

    def hotspot_handle_hit_test(self, hotspot, render_info, x, y):
        return self.handle


class FakeRoot:
    def lift(self):
        pass

    def focus_force(self):
        pass


class FakeDialogs:
    def __init__(self):
        self.warnings = []

    def warning(self, title, message, **_kwargs):
        self.warnings.append((title, message))


class HotspotDragSpies:
    def __init__(self):
        self.render_calls = 0
        self.cursor_calls = 0
        self.editor_calls = []
        self.edit_scene_calls = 0

    def install(self, app) -> None:
        app._render_scene_image = self.render
        app._update_scene_cursor = self.cursor
        app._open_hotspot_editor = self.open_editor
        app.edit_scene = self.edit_scene

    def render(self) -> None:
        self.render_calls += 1

    def cursor(self, *args, **kwargs) -> None:
        self.cursor_calls += 1

    def open_editor(self, hotspot=None, initial_rect=None) -> None:
        self.editor_calls.append({"hotspot": hotspot, "initial_rect": initial_rect})

    def edit_scene(self) -> None:
        self.edit_scene_calls += 1


def _hotspot(hotspot_id: str = "h1") -> HotspotData:
    return HotspotData(
        id=hotspot_id,
        label=hotspot_id,
        x=0.1,
        y=0.2,
        width=0.2,
        height=0.3,
    )


def _app(hotspot=None, handle=None, tool_mode: str = "select"):
    scene = Scene(id="scene_1", title="Scene 1", hotspots=[hotspot] if hotspot is not None else [])
    project = StoryProject(project_name="Hotspot Drag", scenes=[scene])
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
    app.scene_image_view = FakeSceneImageView(hotspot=hotspot, handle=handle)
    app.current_mode = "design"
    app.hotspot_edit_mode = True
    app.hotspot_tool_mode = tool_mode
    app.hotspot_drag_start = None
    app.hotspot_drag_state = None
    app.hotspot_preview_rect = None
    app.selected_hotspot_id = "previous"
    app.root = FakeRoot()
    app.dialogs = FakeDialogs()
    app._hotspot_overlap_warning_open = False
    spies = HotspotDragSpies()
    spies.install(app)
    return app, spies


def _drag_state(mode: str, hotspot, handle: str | None = None, start_local: tuple[int, int] | None = (50, 50)):
    return {
        "mode": mode,
        "handle": handle,
        "hotspot": hotspot,
        "start_local": start_local,
        "origin": {
            "x": float(getattr(hotspot, "x", 0.0)),
            "y": float(getattr(hotspot, "y", 0.0)),
            "width": float(getattr(hotspot, "width", 0.1)),
            "height": float(getattr(hotspot, "height", 0.1)),
        },
    }


def test_scene_click_on_hotspot_without_handle_starts_move_drag():
    hotspot = _hotspot()
    app, spies = _app(hotspot=hotspot, handle=None)
    event = FakeEvent(60, 70)

    app._on_scene_click(event)

    assert app.selected_hotspot_id == "h1"
    assert app.hotspot_drag_start is event
    assert app.hotspot_drag_state["mode"] == "move"
    assert app.hotspot_drag_state["handle"] is None
    assert app.hotspot_drag_state["hotspot"] is hotspot
    assert app.hotspot_drag_state["start_local"] == (40, 40)
    assert app.hotspot_drag_state["origin"] == {
        "x": 0.1,
        "y": 0.2,
        "width": 0.2,
        "height": 0.3,
    }
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1


def test_scene_click_on_hotspot_with_handle_starts_resize_drag():
    hotspot = _hotspot()
    app, spies = _app(hotspot=hotspot, handle="se")
    event = FakeEvent(60, 70)

    app._on_scene_click(event)

    assert app.selected_hotspot_id == "h1"
    assert app.hotspot_drag_state["mode"] == "resize"
    assert app.hotspot_drag_state["handle"] == "se"
    assert app.hotspot_drag_state["hotspot"] is hotspot
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1


def test_scene_click_on_selected_handle_zone_outside_rect_starts_resize_drag():
    hotspot = _hotspot()
    app, spies = _app(hotspot=hotspot)
    app.scene_image_view = SceneImageViewService()
    app.selected_hotspot_id = "h1"
    event = FakeEvent(30, 40)

    app._on_scene_click(event)

    assert app.selected_hotspot_id == "h1"
    assert app.hotspot_drag_state["mode"] == "resize"
    assert app.hotspot_drag_state["handle"] == "nw"
    assert app.hotspot_drag_state["hotspot"] is hotspot
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1


def test_scene_click_empty_area_with_create_tool_starts_create_drag():
    app, spies = _app(hotspot=None, tool_mode="create")
    event = FakeEvent(80, 90)

    app._on_scene_click(event)

    assert app.selected_hotspot_id == ""
    assert app.hotspot_drag_start is event
    assert app.hotspot_drag_state == {"mode": "create"}
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1


def test_scene_click_empty_area_with_select_tool_clears_selection_without_create_drag():
    app, spies = _app(hotspot=None, tool_mode="select")

    app._on_scene_click(FakeEvent(80, 90))

    assert app.selected_hotspot_id == ""
    assert app.hotspot_drag_start is None
    assert app.hotspot_drag_state is None
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1


def test_scene_release_create_drag_with_valid_rect_opens_editor_and_clears_state():
    app, spies = _app(hotspot=None, tool_mode="create")
    app.hotspot_drag_start = FakeEvent(40, 50)
    app.hotspot_drag_state = {"mode": "create"}
    app.hotspot_preview_rect = {"x": 0.1, "y": 0.2, "width": 0.2, "height": 0.2}

    app._on_scene_release(FakeEvent(140, 90))

    assert app.hotspot_drag_start is None
    assert app.hotspot_drag_state is None
    assert app.hotspot_preview_rect is None
    assert spies.editor_calls == [
        {
            "hotspot": None,
            "initial_rect": {"x": 0.1, "y": 0.2, "width": 0.5, "height": 0.4},
        }
    ]
    assert spies.render_calls == 0
    assert spies.cursor_calls == 1


def test_scene_release_create_drag_with_invalid_rect_clears_state_without_opening_editor():
    app, spies = _app(hotspot=None, tool_mode="create")
    app.hotspot_drag_start = FakeEvent(40, 50)
    app.hotspot_drag_state = {"mode": "create"}
    app.hotspot_preview_rect = {"x": 0.1, "y": 0.2, "width": 0.01, "height": 0.01}
    event = FakeEvent(50, 60)

    app._on_scene_release(event)

    assert app.hotspot_drag_start is None
    assert app.hotspot_drag_state is None
    assert app.hotspot_preview_rect is None
    assert spies.editor_calls == []
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1


def test_scene_release_move_drag_clears_state_and_refreshes():
    hotspot = _hotspot()
    app, spies = _app(hotspot=hotspot)
    app.hotspot_drag_start = FakeEvent(60, 70)
    app.hotspot_drag_state = {"mode": "move", "hotspot": hotspot}
    app.hotspot_preview_rect = {"x": 0.1, "y": 0.2, "width": 0.2, "height": 0.2}
    event = FakeEvent(80, 90)

    app._on_scene_release(event)

    assert app.hotspot_drag_start is None
    assert app.hotspot_drag_state is None
    assert app.hotspot_preview_rect is None
    assert spies.editor_calls == []
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1


def test_scene_drag_move_applies_normalized_delta():
    hotspot = _hotspot()
    app, spies = _app(hotspot=hotspot)
    app.hotspot_drag_state = _drag_state("move", hotspot)

    app._on_scene_drag(FakeEvent(90, 90))

    assert hotspot.x == pytest.approx(0.2)
    assert hotspot.y == pytest.approx(0.3)
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1


def test_scene_drag_move_clamps_to_bottom_right_edge():
    hotspot = _hotspot()
    app, spies = _app(hotspot=hotspot)
    app.hotspot_drag_state = _drag_state("move", hotspot)

    app._on_scene_drag(FakeEvent(999, 999))

    assert hotspot.x == pytest.approx(1.0 - hotspot.width)
    assert hotspot.y == pytest.approx(1.0 - hotspot.height)
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1


def test_scene_drag_move_clamps_to_top_left_edge():
    hotspot = _hotspot()
    app, spies = _app(hotspot=hotspot)
    app.hotspot_drag_state = _drag_state("move", hotspot)

    app._on_scene_drag(FakeEvent(-999, -999))

    assert hotspot.x == pytest.approx(0.0)
    assert hotspot.y == pytest.approx(0.0)
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1


def test_scene_drag_resize_se_increases_width_and_height_without_moving_origin():
    hotspot = _hotspot()
    app, spies = _app(hotspot=hotspot)
    app.hotspot_drag_state = _drag_state("resize", hotspot, handle="se")

    app._on_scene_drag(FakeEvent(90, 90))

    assert hotspot.x == pytest.approx(0.1)
    assert hotspot.y == pytest.approx(0.2)
    assert hotspot.width == pytest.approx(0.3)
    assert hotspot.height == pytest.approx(0.4)
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1


def test_scene_drag_resize_nw_moves_origin_and_preserves_bottom_right_edge():
    hotspot = _hotspot()
    original_right = hotspot.x + hotspot.width
    original_bottom = hotspot.y + hotspot.height
    app, spies = _app(hotspot=hotspot)
    app.hotspot_drag_state = _drag_state("resize", hotspot, handle="nw")

    app._on_scene_drag(FakeEvent(90, 90))

    assert hotspot.x == pytest.approx(0.2)
    assert hotspot.y == pytest.approx(0.3)
    assert hotspot.width == pytest.approx(0.1)
    assert hotspot.height == pytest.approx(0.2)
    assert hotspot.x + hotspot.width == pytest.approx(original_right)
    assert hotspot.y + hotspot.height == pytest.approx(original_bottom)
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1


def test_scene_drag_resize_respects_minimum_normalized_size():
    hotspot = _hotspot()
    app, spies = _app(hotspot=hotspot)
    app.hotspot_drag_state = _drag_state("resize", hotspot, handle="nw")

    app._on_scene_drag(FakeEvent(999, 999))

    assert hotspot.width == pytest.approx(0.03)
    assert hotspot.height == pytest.approx(0.03)
    assert hotspot.width >= 0.03
    assert hotspot.height >= 0.03
    assert spies.render_calls == 1
    assert spies.cursor_calls == 1


def test_scene_drag_with_missing_hotspot_or_start_local_does_not_modify_or_render():
    hotspot = _hotspot()
    app, spies = _app(hotspot=hotspot)
    app.hotspot_drag_state = _drag_state("move", hotspot)
    app.hotspot_drag_state["hotspot"] = None

    app._on_scene_drag(FakeEvent(90, 90))

    assert hotspot.x == pytest.approx(0.1)
    assert hotspot.y == pytest.approx(0.2)
    assert spies.render_calls == 0
    assert spies.cursor_calls == 0

    app.hotspot_drag_state = _drag_state("move", hotspot, start_local=None)
    app._on_scene_drag(FakeEvent(90, 90))

    assert hotspot.x == pytest.approx(0.1)
    assert hotspot.y == pytest.approx(0.2)
    assert spies.render_calls == 0
    assert spies.cursor_calls == 0


def test_scene_release_create_drag_rejects_overlap_before_opening_editor():
    existing = _hotspot("existing")
    app, spies = _app(hotspot=existing, tool_mode="create")
    app.hotspot_drag_start = FakeEvent(40, 50)
    app.hotspot_drag_state = {"mode": "create"}

    app._on_scene_release(FakeEvent(100, 90))

    assert spies.editor_calls == []
    assert spies.render_calls == 1
    assert len(app.dialogs.warnings) == 1


def test_scene_release_move_drag_restores_origin_when_hotspots_overlap():
    moving = _hotspot("moving")
    other = _hotspot("other")
    other.x = 0.4
    other.y = 0.2
    app, spies = _app(hotspot=moving)
    app.current_scene.hotspots.append(other)
    app.selected_hotspot_id = "moving"
    app.hotspot_drag_state = _drag_state("move", moving)
    moving.x = 0.45

    app._on_scene_release(FakeEvent(100, 90))

    assert moving.x == pytest.approx(0.1)
    assert moving.y == pytest.approx(0.2)
    assert app.selected_hotspot_id == "moving"
    assert len(app.dialogs.warnings) == 1
    assert spies.render_calls == 1


def test_scene_release_resize_drag_restores_origin_when_hotspots_overlap():
    resizing = _hotspot("resizing")
    other = _hotspot("other")
    other.x = 0.35
    other.y = 0.2
    app, spies = _app(hotspot=resizing)
    app.current_scene.hotspots.append(other)
    app.selected_hotspot_id = "resizing"
    app.hotspot_drag_state = _drag_state("resize", resizing, handle="se")
    resizing.width = 0.4

    app._on_scene_release(FakeEvent(100, 90))

    assert resizing.width == pytest.approx(0.2)
    assert resizing.height == pytest.approx(0.3)
    assert app.selected_hotspot_id == "resizing"
    assert len(app.dialogs.warnings) == 1
    assert spies.render_calls == 1
