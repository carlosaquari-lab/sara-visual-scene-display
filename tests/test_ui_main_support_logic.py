import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.controller import AppController
from app.models import CellData, Scene, StoryProject, default_supports, normalize_supports
from app.ui_main import SaraApp


class FakeBoolVar:
    def __init__(self, value: bool):
        self._value = bool(value)

    def get(self) -> bool:
        return self._value


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
    return app


def test_support_has_content_detects_text_image_and_audio():
    app = object.__new__(SaraApp)

    assert app._support_has_content(_support(0, text="hello")) is True
    assert app._support_has_content(_support(0, image_path="image.png")) is True
    assert app._support_has_content(_support(0, audio_path="audio.wav")) is True


def test_support_has_content_returns_false_for_empty_support():
    app = object.__new__(SaraApp)

    assert app._support_has_content(None) is False
    assert app._support_has_content(_support(0)) is False
    assert app._support_has_content(_support(0, text="   ")) is False


def test_current_scene_has_supports_distinguishes_scene_with_supports_from_empty_scene():
    scene_with_supports = Scene(id="with", title="with", supports=[_support(0, text="support")])
    empty_scene = _empty_scene("empty")
    project = StoryProject(project_name="Support Logic", scenes=[scene_with_supports, empty_scene])
    app = _app(project, scene_with_supports)

    assert app._current_scene_has_supports() is True

    app.current_scene_index = 1
    assert app._current_scene_has_supports() is False


def test_project_has_any_supports_when_any_scene_has_supports_even_if_current_scene_is_empty():
    scene_with_supports = Scene(id="with", title="with", supports=[_support(0, image_path="support.png")])
    empty_scene = _empty_scene("empty")
    project = StoryProject(project_name="Support Logic", scenes=[scene_with_supports, empty_scene])
    app = _app(project, empty_scene)

    assert app._current_scene_has_supports() is False
    assert app._project_has_any_supports() is True


def test_support_counts_reports_total_configured_presented_and_strip_state():
    scene = Scene(
        id="scene",
        title="scene",
        supports=[
            _support(0, text="visible support", visible=True),
            _support(1, image_path="configured.png", visible=False),
            _support(2, audio_path="presented.wav", visible=True),
        ],
    )
    normalize_supports(scene)
    project = StoryProject(project_name="Support Counts", scenes=[scene])
    app = _app(project, scene, strip_on=True)

    counts = app._support_counts()

    assert counts == {
        "support_slots_total": 3,
        "support_slots_configured": 3,
        "support_slots_presented": 2,
        "support_strip_enabled": 1,
    }

    app.support_strip_visible = FakeBoolVar(False)
    counts = app._support_counts()
    assert counts["support_slots_total"] == 3
    assert counts["support_slots_configured"] == 3
    assert counts["support_slots_presented"] == 0
    assert counts["support_strip_enabled"] == 0
