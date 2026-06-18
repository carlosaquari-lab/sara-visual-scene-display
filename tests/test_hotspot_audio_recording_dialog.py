from __future__ import annotations

from pathlib import Path

import app.ui_main  # Ensures the existing service/dialog import graph is initialized.
from app.models import CellData, HotspotData
from app.ui_dialogs import CellEditorDialog, HotspotEditorDialog, RecordHotspotAudioDialog


class FakeLabel:
    def __init__(self):
        self.text = ""

    def configure(self, **kwargs):
        if "text" in kwargs:
            self.text = kwargs["text"]


class FakeWidget:
    def __init__(self):
        self.configured = []
        self.state = None

    def configure(self, **kwargs):
        self.configured.append(kwargs)
        if "state" in kwargs:
            self.state = kwargs["state"]


class FakeSession:
    def __init__(self, path: Path):
        self.path = path
        self.stopped = False
        self.cancelled = False
        self.cancel_remove_file = None

    def stop(self):
        self.stopped = True
        return self.path

    def cancel(self, *, remove_file=True):
        self.cancelled = True
        self.cancel_remove_file = remove_file


def _editor_with_audio(audio_path: str = ""):
    editor = object.__new__(HotspotEditorDialog)
    editor.hotspot = HotspotData(id="hotspot_1", audio_path=audio_path)
    editor.audio_label = FakeLabel()
    editor.audio_preview_button = FakeWidget()
    editor.dialogs = type("FakeDialogs", (), {
        "warnings": [],
        "errors": [],
        "warning": lambda self, title, message, **kwargs: self.warnings.append((title, message)),
        "error": lambda self, title, message, **kwargs: self.errors.append((title, message)),
    })()
    return editor


def _cell_editor_with_audio(audio_path: str = ""):
    editor = object.__new__(CellEditorDialog)
    editor.cell = CellData(id="support_1", position=0, audio_path=audio_path)
    editor.scene_id = "scene_1"
    editor.project_path = ""
    editor.audio_label = FakeLabel()
    editor.audio_preview_button = FakeWidget()
    editor.dialogs = type("FakeDialogs", (), {
        "warnings": [],
        "errors": [],
        "warning": lambda self, title, message, **kwargs: self.warnings.append((title, message)),
        "error": lambda self, title, message, **kwargs: self.errors.append((title, message)),
    })()
    return editor


def _record_dialog(session: FakeSession, on_recorded):
    dialog = object.__new__(RecordHotspotAudioDialog)
    dialog._session = session
    dialog.status_label = FakeWidget()
    dialog.start_button = FakeWidget()
    dialog.stop_button = FakeWidget()
    dialog.preview_button = FakeWidget()
    dialog.use_button = FakeWidget()
    dialog.on_recorded = on_recorded
    dialog.destroyed = False
    dialog.dialogs = None
    dialog.destroy = lambda: setattr(dialog, "destroyed", True)
    return dialog


def test_hotspot_editor_apply_recorded_audio_updates_audio_path_and_label(tmp_path):
    editor = _editor_with_audio("old.wav")
    new_audio = tmp_path / "hotspot_scene_1_hotspot_1_stamp.wav"

    editor._apply_recorded_audio(new_audio)

    assert editor.hotspot.audio_path == str(new_audio)
    assert editor.audio_label.text == new_audio.name


def test_record_hotspot_audio_cancel_keeps_previous_hotspot_audio(tmp_path):
    editor = _editor_with_audio("previous.wav")
    recorded = []
    session = FakeSession(tmp_path / "new.wav")
    dialog = _record_dialog(session, lambda path: recorded.append(path))

    dialog.cancel()

    assert editor.hotspot.audio_path == "previous.wav"
    assert recorded == []
    assert session.cancelled is True
    assert session.cancel_remove_file is True
    assert dialog.destroyed is True


def test_record_hotspot_audio_stop_prepares_new_audio_without_auto_saving_project(tmp_path):
    project_json = tmp_path / "project.json"
    original_json = '{"project_name": "Demo", "scenes": []}'
    project_json.write_text(original_json, encoding="utf-8")
    editor = _editor_with_audio("previous.wav")
    new_audio = tmp_path / "recordings" / "new.wav"
    session = FakeSession(new_audio)
    dialog = _record_dialog(session, editor._apply_recorded_audio)

    dialog.stop_recording()

    assert session.stopped is True
    assert editor.hotspot.audio_path == "previous.wav"
    assert editor.audio_label.text == ""
    assert project_json.read_text(encoding="utf-8") == original_json
    assert dialog.preview_button.state == "normal"
    assert dialog.use_button.state == "normal"
    assert dialog.destroyed is False

def test_hotspot_editor_apply_preserves_recorded_audio_path():
    saved = []
    editor = _editor_with_audio("previous.wav")
    editor.text_var = type("FakeVar", (), {"get": lambda self: "hello"})()
    editor.tts_var = type("FakeVar", (), {"get": lambda self: True})()
    editor.visible_var = type("FakeVar", (), {"get": lambda self: True})()
    editor.target_scene_var = type("FakeVar", (), {"get": lambda self: ""})()
    editor.typology_var = type("FakeVar", (), {"get": lambda self: ""})()
    editor.discourse_var = type("FakeVar", (), {"get": lambda self: ""})()
    editor.label_bg_var = type("FakeVar", (), {"get": lambda self: "#FFFFFF"})()
    editor.label_fg_var = type("FakeVar", (), {"get": lambda self: "#000000"})()
    editor.label_size_var = type("FakeVar", (), {"get": lambda self: 16})()
    editor.label_persistence_seconds_var = type("FakeVar", (), {"get": lambda self: 5})()
    editor.label_persistence_always_var = type("FakeVar", (), {"get": lambda self: False})()
    editor.scene_id_by_label = {}
    editor.typology_id_by_label = {}
    editor.discourse_id_by_label = {}
    editor.on_save = lambda hotspot: saved.append(hotspot)
    editor.destroyed = False
    editor.destroy = lambda: setattr(editor, "destroyed", True)

    editor._apply_recorded_audio("recorded.wav")
    editor.apply()

    assert saved[0].audio_path == "recorded.wav"
    assert editor.destroyed is True

def test_hotspot_editor_refresh_preview_button_tracks_audio_presence():
    editor = _editor_with_audio("")

    editor._refresh_audio_preview_button()
    assert editor.audio_preview_button.state == "disabled"


def test_cell_editor_apply_recorded_audio_updates_audio_path_and_label(tmp_path):
    editor = _cell_editor_with_audio("old.wav")
    new_audio = tmp_path / "hotspot_scene_1_support_1_stamp.wav"

    editor._apply_recorded_audio(new_audio)

    assert editor.cell.audio_path == str(new_audio)
    assert editor.audio_label.text == new_audio.name
    assert editor.audio_preview_button.state == "normal"


def test_cell_editor_refresh_preview_button_tracks_audio_presence():
    editor = _cell_editor_with_audio("")

    editor._refresh_audio_preview_button()
    assert editor.audio_preview_button.state == "disabled"

    editor._apply_recorded_audio("recorded.wav")
    assert editor.audio_preview_button.state == "normal"

    editor.clear_audio()
    assert editor.audio_preview_button.state == "disabled"


def test_cell_editor_play_preview_uses_audio_player_for_existing_file(tmp_path):
    audio_path = tmp_path / "support.wav"
    audio_path.write_bytes(b"wav")
    editor = _cell_editor_with_audio(str(audio_path))
    played = []
    editor._play_audio_file = lambda path: played.append(str(path)) or True

    editor.play_audio_preview()

    assert played == [str(audio_path)]
    assert editor.dialogs.warnings == []
    assert editor.dialogs.errors == []


def test_cell_editor_play_preview_warns_when_audio_missing():
    editor = _cell_editor_with_audio("missing.wav")

    editor.play_audio_preview()

    assert editor.dialogs.warnings

    editor._apply_recorded_audio("recorded.wav")
    assert editor.audio_preview_button.state == "normal"

    editor.clear_audio()
    assert editor.audio_preview_button.state == "disabled"


def test_hotspot_editor_play_preview_uses_audio_player_for_existing_file(tmp_path):
    audio_path = tmp_path / "preview.wav"
    audio_path.write_bytes(b"wav")
    editor = _editor_with_audio(str(audio_path))
    played = []
    editor._play_audio_file = lambda path: played.append(str(path)) or True

    editor.play_audio_preview()

    assert played == [str(audio_path)]
    assert editor.dialogs.warnings == []
    assert editor.dialogs.errors == []


def test_hotspot_editor_play_preview_warns_when_audio_missing():
    editor = _editor_with_audio("missing.wav")

    editor.play_audio_preview()

    assert editor.dialogs.warnings


def test_record_dialog_stop_enables_preview_and_use_without_closing(tmp_path):
    recorded = []
    session = FakeSession(tmp_path / "new.wav")
    dialog = _record_dialog(session, lambda path: recorded.append(path))

    dialog.stop_recording()

    assert recorded == []
    assert dialog.preview_button.state == "normal"
    assert dialog.use_button.state == "normal"
    assert dialog.stop_button.state == "disabled"
    assert dialog.start_button.state == "normal"
    assert dialog.destroyed is False


def test_record_dialog_play_preview_uses_injected_audio_player(tmp_path):
    audio_path = tmp_path / "new.wav"
    audio_path.write_bytes(b"wav")
    played = []
    dialog = _record_dialog(FakeSession(audio_path), lambda _path: None)
    dialog._recorded_path = audio_path
    dialog.audio_player = type("FakePlayer", (), {"play_file": lambda self, path: played.append(path) or True})()

    dialog.play_preview()

    assert played == [str(audio_path)]

def test_record_dialog_use_recording_applies_audio_and_closes(tmp_path):
    audio_path = tmp_path / "new.wav"
    audio_path.write_bytes(b"wav")
    recorded = []
    dialog = _record_dialog(FakeSession(audio_path), lambda path: recorded.append(path))
    dialog._recorded_path = audio_path

    dialog.use_recording()

    assert recorded == [audio_path]
    assert dialog.destroyed is True


def test_record_dialog_window_close_behaves_like_cancel(tmp_path):
    recorded = []
    session = FakeSession(tmp_path / "new.wav")
    dialog = _record_dialog(session, lambda path: recorded.append(path))
    dialog._recorded_path = tmp_path / "new.wav"

    dialog.cancel()

    assert recorded == []
    assert session.cancelled is True
    assert dialog.destroyed is True
