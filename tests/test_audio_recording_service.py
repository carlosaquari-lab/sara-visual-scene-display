from __future__ import annotations

from pathlib import Path

from app.services.audio_recording_service import (
    ensure_recording_dir,
    fallback_recordings_dir,
    project_audio_assets_dir,
    recording_destination_dir,
    recording_filename,
    recording_path_for_hotspot,
)


def test_recording_filename_uses_hotspot_scene_timestamp_and_is_unique():
    first = recording_filename("scene 1", "hotspot/one", "20260505_120000_000001")
    second = recording_filename("scene 1", "hotspot/one", "20260505_120000_000002")

    assert first == "hotspot_scene_1_hotspot_one_20260505_120000_000001.wav"
    assert second == "hotspot_scene_1_hotspot_one_20260505_120000_000002.wav"
    assert first != second


def test_recording_filename_always_uses_wav_extension():
    assert recording_filename("scene", "hotspot", "stamp").endswith(".wav")


def test_recording_destination_uses_existing_project_audio_assets(tmp_path):
    project_path = tmp_path / "Demo Project.json"
    project_path.write_text('{"project_name": "Demo"}', encoding="utf-8")
    assets_audio = project_audio_assets_dir(project_path)
    assets_audio.mkdir(parents=True)

    destination = recording_destination_dir(project_path, base_audio_dir=tmp_path / "global_audio")

    assert destination == assets_audio


def test_recording_destination_falls_back_to_controlled_recordings_dir(tmp_path):
    project_path = tmp_path / "Unsaved Assets.json"
    project_path.write_text('{"project_name": "Demo"}', encoding="utf-8")
    base_audio = tmp_path / "sarab_data" / "audio"

    destination = recording_destination_dir(project_path, base_audio_dir=base_audio)

    assert destination == fallback_recordings_dir(base_audio)


def test_recording_path_creates_destination_folder(tmp_path):
    base_audio = tmp_path / "audio"

    path = recording_path_for_hotspot(
        "scene_1",
        "hotspot_1",
        None,
        base_audio_dir=base_audio,
        timestamp="20260505_120000_000001",
    )

    assert path.parent.exists()
    assert path.parent == base_audio / "recordings"
    assert path.name == "hotspot_scene_1_hotspot_1_20260505_120000_000001.wav"


def test_ensure_recording_dir_creates_folder(tmp_path):
    target = tmp_path / "nested" / "recordings"

    created = ensure_recording_dir(target)

    assert created == target
    assert target.exists()
    assert target.is_dir()


def test_recording_path_helpers_do_not_modify_project_json(tmp_path):
    project_path = tmp_path / "Project.json"
    original = '{"project_name": "Demo", "scenes": []}'
    project_path.write_text(original, encoding="utf-8")
    assets_audio = project_audio_assets_dir(project_path)
    assets_audio.mkdir(parents=True)

    _ = recording_path_for_hotspot(
        "scene_1",
        "hotspot_1",
        project_path,
        base_audio_dir=tmp_path / "audio",
        timestamp="20260505_120000_000001",
    )

    assert project_path.read_text(encoding="utf-8") == original
    assert list(tmp_path.glob("*.json")) == [project_path]