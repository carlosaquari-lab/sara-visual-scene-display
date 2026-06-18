from __future__ import annotations

from pathlib import Path

from app.controller import AppController
from app.models import HotspotData, Scene, StoryProject
from app.services.session_service import SessionService
from app.storage import load_project, save_project
from app.ui_main import SaraApp


class FakeAudio:
    def __init__(self):
        self.calls = []

    def play_or_speak(self, audio_path, text, tts_enabled=True):
        self.calls.append({"audio_path": audio_path, "text": text, "tts_enabled": tts_enabled})
        return "file" if audio_path else "tts"


class FakeResearch:
    def __init__(self):
        self.events = []

    def log_event(self, **kwargs):
        self.events.append(kwargs)


class FakeUsers:
    current_user_id = ""
    user_segment_key_presses = 0
    user_segment_words_inserted = 0
    user_segment_characters_inserted = 0

    def get_current_user_name(self):
        return ""


class FakeRoot:
    def after(self, _delay, callback):
        callback()
        return "after-id"


class FakeDialog:
    instances = []

    def __init__(self, _root, hotspot, _scene_choices, on_save, **_kwargs):
        self.hotspot = HotspotData.from_dict(hotspot.to_dict())
        self.on_save = on_save
        FakeDialog.instances.append(self)

    def bind(self, *_args, **_kwargs):
        return None

    def apply_recorded_and_save(self, audio_path: str):
        self.hotspot.audio_path = audio_path
        self.on_save(self.hotspot)


def test_open_hotspot_editor_apply_updates_real_scene_hotspot_audio_path(monkeypatch):
    import app.ui_main as ui_main

    original = HotspotData(id="h1", label="H", text="hello", audio_path="")
    scene = Scene(id="scene_1", title="Scene 1", hotspots=[original])
    project = StoryProject(project_name="Project", scenes=[scene])
    app = object.__new__(SaraApp)
    app.root = FakeRoot()
    app.controller = AppController()
    app.controller.project = project
    app.controller.current_scene_index = 0
    app.current_mode = "design"
    app.hotspot_preview_rect = None
    app.hotspot_drag_start = None
    app.hotspot_drag_state = None
    app.selected_hotspot_id = ""
    app.scene_image_frame = object()
    app._scene_choice_pairs = lambda: [("", "None")]
    app._render_scene_image = lambda: None
    app._update_scene_cursor = lambda: None
    FakeDialog.instances = []
    monkeypatch.setattr(ui_main, "HotspotEditorDialog", FakeDialog)

    app._open_hotspot_editor(original)
    FakeDialog.instances[0].apply_recorded_and_save("recorded.wav")

    assert app.current_scene.hotspots[0].audio_path == "recorded.wav"
    assert app.current_scene.hotspots[0].id == "h1"
    assert app.selected_hotspot_id == "h1"


def test_controller_activate_hotspot_returns_recorded_audio_path_in_user_mode():
    controller = AppController()
    hotspot = HotspotData(id="h1", label="Label", text="hello", audio_path="recorded.wav", tts_enabled=True)
    controller.project = StoryProject(project_name="Project", scenes=[Scene(id="scene_1", title="Scene 1", hotspots=[hotspot])])
    controller.current_scene_index = 0
    controller.set_mode("user")

    result = controller.activate_hotspot(hotspot, "")

    assert result.action == "insert"
    assert result.audio_path == "recorded.wav"
    assert result.speak_text == "HELLO"
    assert result.tts_enabled is True


def test_session_service_activate_hotspot_passes_audio_path_to_audio_manager_and_prefers_file():
    controller = AppController()
    hotspot = HotspotData(id="h1", label="Label", text="hello", audio_path="recorded.wav", tts_enabled=True)
    scene = Scene(id="scene_1", title="Scene 1", hotspots=[hotspot])
    project = StoryProject(project_name="Project", scenes=[scene])
    controller.project = project
    controller.current_scene_index = 0
    controller.set_mode("user")
    audio = FakeAudio()
    research = FakeResearch()
    service = SessionService(controller, audio, research, FakeUsers())

    result = service.activate_hotspot(project, scene, 0, "user", hotspot, "")

    assert result.audio_path == "recorded.wav"
    assert audio.calls == [{"audio_path": "recorded.wav", "text": "HELLO", "tts_enabled": True}]
    assert any(event.get("action") == "audio_play" and event.get("audio_source") == "file" for event in research.events)

def test_recorded_hotspot_audio_is_copied_to_project_assets_and_resolves_after_load(tmp_path):
    source_audio = tmp_path / "recordings" / "recorded.wav"
    source_audio.parent.mkdir(parents=True)
    source_audio.write_bytes(b"recorded audio bytes")
    hotspot = HotspotData(id="h1", label="Label", text="hello", audio_path=str(source_audio), tts_enabled=True)
    scene = Scene(id="scene_1", title="Scene 1", hotspots=[hotspot])
    project = StoryProject(project_name="Project", scenes=[scene])
    project_path = tmp_path / "Project.json"

    before_save_audio_path = hotspot.audio_path
    save_project(project, str(project_path))
    import json
    payload = json.loads(project_path.read_text(encoding="utf-8"))
    json_audio_path = payload["scenes"][0]["hotspots"][0]["audio_path"]
    copied_audio = (project_path.parent / json_audio_path).resolve()
    loaded = load_project(str(project_path))
    loaded_hotspot = loaded.scenes[0].hotspots[0]
    audio = FakeAudio()
    research = FakeResearch()
    controller = AppController()
    controller.project = loaded
    controller.current_scene_index = 0
    controller.set_mode("user")
    service = SessionService(controller, audio, research, FakeUsers())

    service.activate_hotspot(loaded, loaded.scenes[0], 0, "user", loaded_hotspot, "")

    assert before_save_audio_path == str(source_audio)
    assert json_audio_path == str(Path("Project_assets") / "audio" / "recorded.wav")
    assert not Path(json_audio_path).is_absolute()
    assert copied_audio.exists()
    assert copied_audio.read_bytes() == b"recorded audio bytes"
    assert loaded_hotspot.audio_path == str(copied_audio)
    assert Path(loaded_hotspot.audio_path).exists()
    assert audio.calls[0]["audio_path"] == str(copied_audio)
    assert Path(audio.calls[0]["audio_path"]).exists()