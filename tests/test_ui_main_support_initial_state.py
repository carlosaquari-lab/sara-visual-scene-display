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


class ReserveSpy:
    def __init__(self):
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1


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
    reserve_spy = ReserveSpy()
    app._reserve_or_hide_support_bar = reserve_spy
    return app, reserve_spy


def test_set_support_strip_from_current_scene_enables_strip_when_support_is_visible():
    scene = Scene(id="visible", title="visible", supports=[_support(0, visible=True)])
    project = StoryProject(project_name="Support Initial State", scenes=[scene])
    app, reserve_spy = _app(project, scene)

    app._set_support_strip_from_current_scene()

    assert app.support_strip_visible.get() is True
    assert app.support_strip_visible.set_calls == [True]
    assert reserve_spy.calls == 0


def test_set_support_strip_from_current_scene_ignores_content_when_support_is_not_visible():
    scene = Scene(id="content", title="content", supports=[_support(0, text="configured", visible=False)])
    project = StoryProject(project_name="Support Initial State", scenes=[scene])
    app, reserve_spy = _app(project, scene, strip_on=True)

    app._set_support_strip_from_current_scene()

    assert app.support_strip_visible.get() is False
    assert app.support_strip_visible.set_calls == [False]
    assert reserve_spy.calls == 1


def test_set_support_strip_from_current_scene_disables_strip_when_no_support_is_visible():
    scene = _empty_scene("empty")
    project = StoryProject(project_name="Support Initial State", scenes=[scene])
    app, reserve_spy = _app(project, scene, strip_on=True)

    app._set_support_strip_from_current_scene()

    assert app.support_strip_visible.get() is False
    assert app.support_strip_visible.set_calls == [False]
    assert reserve_spy.calls == 1


def test_set_support_strip_from_current_scene_updates_state_after_scene_index_changes():
    visible_scene = Scene(id="visible", title="visible", supports=[_support(0, visible=True)])
    empty_scene = _empty_scene("empty")
    project = StoryProject(project_name="Support Initial State", scenes=[visible_scene, empty_scene])
    app, reserve_spy = _app(project, visible_scene)

    app._set_support_strip_from_current_scene()
    assert app.support_strip_visible.get() is True

    app.current_scene_index = 1
    app._set_support_strip_from_current_scene()

    assert app.support_strip_visible.get() is False
    assert app.support_strip_visible.set_calls == [True, False]
    assert reserve_spy.calls == 1
