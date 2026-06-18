import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.controller import AppController
from app.models import CellData, Scene, StoryProject, default_supports, normalize_supports
from app.ui_main import SaraApp


class FakeBoolVar:
    def __init__(self, value: bool = False):
        self._value = bool(value)
        self.set_calls = []

    def get(self) -> bool:
        return self._value

    def set(self, value: bool) -> None:
        self._value = bool(value)
        self.set_calls.append(bool(value))


class SupportStripSpies:
    def __init__(self):
        self.render_calls = 0
        self.clear_calls = 0
        self.reserve_calls = 0

    def install(self, app) -> None:
        app._render_support_strip = self.render
        app._clear_support_widget_cache = self.clear
        app._reserve_or_hide_support_bar = self.reserve

    def render(self) -> None:
        self.render_calls += 1

    def clear(self) -> None:
        self.clear_calls += 1

    def reserve(self) -> None:
        self.reserve_calls += 1


def _support(
    index: int,
    text: str = "",
    image_path: str = "",
    audio_path: str = "",
    visible: bool = False,
) -> CellData:
    return CellData(
        id=f"support_{index + 1}",
        position=index,
        text=text,
        image_path=image_path,
        audio_path=audio_path,
        cell_type="visual_support",
        visible=visible,
    )


def _empty_scene(scene_id: str) -> Scene:
    scene = Scene(id=scene_id, title=scene_id, supports=default_supports())
    normalize_supports(scene)
    for support in scene.supports:
        support.text = ""
        support.image_path = ""
        support.audio_path = ""
        support.visible = False
    return scene


def _app(project: StoryProject, current_scene: Scene, strip_on: bool = False):
    app = object.__new__(SaraApp)
    app.controller = AppController()
    app.controller.project = project
    app.controller.current_scene_index = project.scenes.index(current_scene)
    app.support_strip_visible = FakeBoolVar(strip_on)
    spies = SupportStripSpies()
    spies.install(app)
    return app, spies


def test_sync_support_strip_renders_when_current_scene_has_support():
    scene_with_support = Scene(id="with", title="with", supports=[_support(0, text="support")])
    empty_scene = _empty_scene("empty")
    project = StoryProject(project_name="Support Sync", scenes=[scene_with_support, empty_scene])
    app, spies = _app(project, scene_with_support, strip_on=True)

    app._sync_support_strip_for_scene_navigation()

    assert app.support_strip_visible.get() is True
    assert app.support_strip_visible.set_calls == []
    assert spies.render_calls == 1
    assert spies.clear_calls == 0


def test_sync_support_strip_clears_empty_scene_but_reserves_when_project_has_supports():
    scene_with_support = Scene(id="with", title="with", supports=[_support(0, image_path="support.png")])
    empty_scene = _empty_scene("empty")
    project = StoryProject(project_name="Support Sync", scenes=[scene_with_support, empty_scene])
    app, spies = _app(project, empty_scene, strip_on=True)

    app._sync_support_strip_for_scene_navigation()

    assert app.support_strip_visible.get() is True
    assert app.support_strip_visible.set_calls == []
    assert spies.clear_calls == 1
    assert spies.reserve_calls == 1
    assert spies.render_calls == 0


def test_sync_support_strip_does_not_keep_old_supports_after_switching_to_empty_scene():
    scene_with_support = Scene(id="with", title="with", supports=[_support(0, audio_path="support.wav")])
    empty_scene = _empty_scene("empty")
    project = StoryProject(project_name="Support Sync", scenes=[scene_with_support, empty_scene])
    app, spies = _app(project, scene_with_support, strip_on=True)

    app.current_scene_index = 1
    app._sync_support_strip_for_scene_navigation()

    assert app.current_scene is empty_scene
    assert app.support_strip_visible.get() is True
    assert spies.render_calls == 0
    assert spies.clear_calls == 1


def test_sync_support_strip_renders_visible_support_without_content():
    scene = Scene(id="visible", title="visible", supports=[_support(0, visible=True)])
    project = StoryProject(project_name="Support Sync", scenes=[scene])
    app, spies = _app(project, scene, strip_on=True)

    app._sync_support_strip_for_scene_navigation()

    assert app.support_strip_visible.get() is True
    assert spies.render_calls == 1
    assert spies.clear_calls == 0


def test_sync_support_strip_keeps_supports_hidden_across_scene_navigation_until_reenabled():
    first_scene = Scene(id="first", title="first", supports=[_support(0, text="first")])
    second_scene = Scene(id="second", title="second", supports=[_support(0, text="second")])
    project = StoryProject(project_name="Support Sync", scenes=[first_scene, second_scene])
    app, spies = _app(project, first_scene, strip_on=False)

    app.current_scene_index = 1
    app._sync_support_strip_for_scene_navigation()

    assert app.current_scene is second_scene
    assert app.support_strip_visible.get() is False
    assert app.support_strip_visible.set_calls == []
    assert spies.render_calls == 0
    assert spies.clear_calls == 1
    assert spies.reserve_calls == 1

    app.support_strip_visible.set(True)
    app._sync_support_strip_for_scene_navigation()

    assert app.support_strip_visible.get() is True
    assert spies.render_calls == 1
