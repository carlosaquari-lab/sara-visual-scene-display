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


class FakeSceneImageView:
    def __init__(self, hotspot=None):
        self.hotspot = hotspot
        self.calls = []

    def hotspot_hit_test(self, hotspots, render_info, x, y):
        self.calls.append({"hotspots": hotspots, "render_info": render_info, "x": x, "y": y})
        if not render_info:
            return None
        image_x = int(render_info.get("image_x", 0))
        image_y = int(render_info.get("image_y", 0))
        display_w = int(render_info.get("display_width", 0))
        display_h = int(render_info.get("display_height", 0))
        local_x = x - image_x
        local_y = y - image_y
        if local_x < 0 or local_y < 0 or local_x > display_w or local_y > display_h:
            return None
        return self.hotspot


class UserClickSpies:
    def __init__(self):
        self.activate_calls = []
        self.audio_calls = 0
        self.edit_scene_calls = 0

    def install(self, app) -> None:
        app.activate_hotspot = self.activate_hotspot
        app.play_scene_audio = self.play_scene_audio
        app.edit_scene = self.edit_scene

    def activate_hotspot(self, hotspot) -> None:
        self.activate_calls.append(hotspot)

    def play_scene_audio(self) -> None:
        self.audio_calls += 1

    def edit_scene(self) -> None:
        self.edit_scene_calls += 1


def _hotspot(hotspot_id: str = "h1") -> HotspotData:
    return HotspotData(id=hotspot_id, label="Help", text="help")


def _app(hotspot=None, render_info=None, scene_audio: str = ""):
    scene = Scene(id="scene_1", title="Scene 1", hotspots=[hotspot] if hotspot is not None else [])
    scene.scene_audio = scene_audio
    project = StoryProject(project_name="Hotspot User Click", scenes=[scene])
    app = object.__new__(SaraApp)
    app.controller = AppController()
    app.controller.project = project
    app.controller.current_scene_index = 0
    app.current_mode = "user"
    app.scene_render_info = render_info
    app.scene_image_view = FakeSceneImageView(hotspot=hotspot)
    spies = UserClickSpies()
    spies.install(app)
    return app, spies


def _valid_render_info():
    return {
        "image_x": 20,
        "image_y": 30,
        "display_width": 200,
        "display_height": 100,
    }


def test_scene_click_user_mode_with_hotspot_activates_hotspot_without_scene_audio():
    hotspot = _hotspot()
    app, spies = _app(hotspot=hotspot, render_info=_valid_render_info())

    app._on_scene_click(FakeEvent(80, 70))

    assert spies.activate_calls == [hotspot]
    assert spies.audio_calls == 0


def test_scene_click_user_mode_outside_rendered_image_does_not_activate_or_play_audio():
    hotspot = _hotspot()
    app, spies = _app(hotspot=hotspot, render_info=_valid_render_info())

    app._on_scene_click(FakeEvent(999, 999))

    assert spies.activate_calls == []
    assert spies.audio_calls == 0


def test_scene_click_user_mode_inside_image_without_hotspot_does_not_play_scene_audio():
    app, spies = _app(hotspot=None, render_info=_valid_render_info())

    app._on_scene_click(FakeEvent(80, 70))

    assert spies.activate_calls == []
    assert spies.audio_calls == 0


def test_scene_click_user_mode_without_valid_render_info_does_not_activate_or_play_audio():
    hotspot = _hotspot()
    app, spies = _app(hotspot=hotspot, render_info=None)

    app._on_scene_click(FakeEvent(80, 70))

    assert spies.activate_calls == []
    assert spies.audio_calls == 0


def test_scene_audio_button_user_mode_with_scene_audio_plays_scene_audio():
    app, spies = _app(scene_audio="scene.wav")
    app.current_mode = "user"

    app._handle_scene_audio_button()

    assert spies.edit_scene_calls == 0
    assert spies.audio_calls == 1


def test_scene_audio_button_design_mode_without_scene_audio_opens_scene_editor():
    app, spies = _app(scene_audio="")
    app.current_mode = "design"

    app._handle_scene_audio_button()

    assert spies.edit_scene_calls == 1
    assert spies.audio_calls == 0
