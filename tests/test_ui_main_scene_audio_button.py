import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.controller import AppController
from app.models import Scene, StoryProject
from app.ui_main import SaraApp


class FakeSceneAudioButton:
    def __init__(self):
        self.place_calls = []
        self.lift_calls = 0
        self.place_forget_calls = 0

    def place(self, *args, **kwargs) -> None:
        self.place_calls.append({"args": args, "kwargs": kwargs})

    def lift(self) -> None:
        self.lift_calls += 1

    def place_forget(self) -> None:
        self.place_forget_calls += 1


class SceneAudioSpies:
    def __init__(self):
        self.play_scene_audio_calls = 0
        self.edit_scene_calls = 0

    def install(self, app) -> None:
        app.play_scene_audio = self.play_scene_audio
        app.edit_scene = self.edit_scene

    def play_scene_audio(self) -> None:
        self.play_scene_audio_calls += 1

    def edit_scene(self) -> None:
        self.edit_scene_calls += 1


def _project(*scene_audio_values: str) -> StoryProject:
    scenes = []
    for index, scene_audio in enumerate(scene_audio_values or ("",), start=1):
        scene = Scene(id=f"scene_{index}", title=f"Scene {index}")
        scene.scene_audio = scene_audio
        scenes.append(scene)
    return StoryProject(project_name="Scene Audio Button", scenes=scenes)


def _app(mode: str = "design", *scene_audio_values: str, current_scene_index: int = 0):
    app = object.__new__(SaraApp)
    app.controller = AppController()
    app.controller.project = _project(*scene_audio_values)
    app.controller.current_scene_index = current_scene_index
    app.current_mode = mode
    app.scene_audio_button = FakeSceneAudioButton()
    spies = SceneAudioSpies()
    spies.install(app)
    return app, spies


def test_scene_audio_button_design_without_scene_audio_is_visible_and_opens_editor():
    app, spies = _app("design", "")

    app._refresh_scene_audio_button_visibility()
    app._handle_scene_audio_button()

    assert len(app.scene_audio_button.place_calls) == 1
    assert app.scene_audio_button.lift_calls == 1
    assert app.scene_audio_button.place_forget_calls == 0
    assert spies.edit_scene_calls == 1
    assert spies.play_scene_audio_calls == 0


def test_scene_audio_button_design_with_scene_audio_is_visible_and_plays_audio():
    app, spies = _app("design", "scene.wav")

    app._refresh_scene_audio_button_visibility()
    app._handle_scene_audio_button()

    assert len(app.scene_audio_button.place_calls) == 1
    assert app.scene_audio_button.lift_calls == 1
    assert app.scene_audio_button.place_forget_calls == 0
    assert spies.play_scene_audio_calls == 1
    assert spies.edit_scene_calls == 0


def test_scene_audio_button_user_without_scene_audio_is_hidden_and_handler_does_nothing_if_called_directly():
    app, spies = _app("user", "")

    app._refresh_scene_audio_button_visibility()
    app._handle_scene_audio_button()

    assert app.scene_audio_button.place_calls == []
    assert app.scene_audio_button.lift_calls == 0
    assert app.scene_audio_button.place_forget_calls == 1
    assert spies.play_scene_audio_calls == 0
    assert spies.edit_scene_calls == 0


def test_scene_audio_button_user_with_scene_audio_is_visible_and_plays_audio():
    app, spies = _app("user", "scene.wav")

    app._refresh_scene_audio_button_visibility()
    app._handle_scene_audio_button()

    assert len(app.scene_audio_button.place_calls) == 1
    assert app.scene_audio_button.lift_calls == 1
    assert app.scene_audio_button.place_forget_calls == 0
    assert spies.play_scene_audio_calls == 1
    assert spies.edit_scene_calls == 0


def test_scene_audio_button_visibility_updates_when_user_mode_scene_changes():
    app, _spies = _app("user", "scene.wav", "", current_scene_index=0)

    app._refresh_scene_audio_button_visibility()
    assert len(app.scene_audio_button.place_calls) == 1
    assert app.scene_audio_button.place_forget_calls == 0

    app.current_scene_index = 1
    app._refresh_scene_audio_button_visibility()

    assert len(app.scene_audio_button.place_calls) == 1
    assert app.scene_audio_button.place_forget_calls == 1
