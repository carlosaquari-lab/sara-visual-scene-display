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


class FakeUIStateService:
    def __init__(self):
        self.update_navigation_calls = []

    def update_navigation_buttons(self, prev_button, next_button, current_scene_index, total_scenes) -> None:
        self.update_navigation_calls.append(
            {
                "prev_button": prev_button,
                "next_button": next_button,
                "current_scene_index": current_scene_index,
                "total_scenes": total_scenes,
            }
        )


def _project(scene_audio: str = "", scene_count: int = 1) -> StoryProject:
    scenes = [Scene(id=f"scene_{idx}", title=f"Scene {idx}") for idx in range(1, scene_count + 1)]
    scenes[0].scene_audio = scene_audio
    return StoryProject(project_name="Mode Aux Visibility", scenes=scenes)


def _app(mode: str = "design", scene_audio: str = "", scene_count: int = 1, with_audio_button: bool = True):
    app = object.__new__(SaraApp)
    app.controller = AppController()
    app.controller.project = _project(scene_audio=scene_audio, scene_count=scene_count)
    app.controller.current_scene_index = 0
    app.current_mode = mode
    if with_audio_button:
        app.scene_audio_button = FakeSceneAudioButton()
    return app


def test_refresh_scene_audio_button_visibility_design_without_scene_audio_shows_button():
    app = _app(mode="design", scene_audio="")

    app._refresh_scene_audio_button_visibility()

    assert len(app.scene_audio_button.place_calls) == 1
    assert app.scene_audio_button.lift_calls == 1
    assert app.scene_audio_button.place_forget_calls == 0


def test_refresh_scene_audio_button_visibility_user_without_scene_audio_hides_button():
    app = _app(mode="user", scene_audio="")

    app._refresh_scene_audio_button_visibility()

    assert app.scene_audio_button.place_calls == []
    assert app.scene_audio_button.lift_calls == 0
    assert app.scene_audio_button.place_forget_calls == 1


def test_refresh_scene_audio_button_visibility_user_with_scene_audio_shows_button():
    app = _app(mode="user", scene_audio="scene.wav")

    app._refresh_scene_audio_button_visibility()

    assert len(app.scene_audio_button.place_calls) == 1
    assert app.scene_audio_button.lift_calls == 1
    assert app.scene_audio_button.place_forget_calls == 0


def test_refresh_scene_audio_button_visibility_without_button_does_not_fail():
    app = _app(mode="design", scene_audio="scene.wav", with_audio_button=False)

    app._refresh_scene_audio_button_visibility()


def test_update_navigation_state_delegates_to_ui_state_service_with_buttons_index_and_total():
    app = _app(mode="design", scene_count=3)
    app.controller.current_scene_index = 1
    app.prev_button = object()
    app.next_button = object()
    app.ui_state_service = FakeUIStateService()

    app._update_navigation_state()

    assert app.ui_state_service.update_navigation_calls == [
        {
            "prev_button": app.prev_button,
            "next_button": app.next_button,
            "current_scene_index": 1,
            "total_scenes": 3,
        }
    ]
