from __future__ import annotations

import json

import pytest

from app import utils


def _temporary_files(directory):
    return list(directory.glob(".*.tmp"))


def test_save_json_replaces_destination_after_successful_write(tmp_path):
    destination = tmp_path / "project.json"
    destination.write_text('{"old": true}', encoding="utf-8")

    utils.save_json(str(destination), {"new": True})

    assert json.loads(destination.read_text(encoding="utf-8")) == {"new": True}
    assert _temporary_files(tmp_path) == []


def test_save_json_preserves_unicode(tmp_path):
    destination = tmp_path / "project.json"

    utils.save_json(str(destination), {"title": "Preparación de pasta 🍝"})

    text = destination.read_text(encoding="utf-8")
    assert "Preparación de pasta 🍝" in text
    assert json.loads(text) == {"title": "Preparación de pasta 🍝"}


def test_save_json_serialization_failure_preserves_original_and_removes_temporary(tmp_path, monkeypatch):
    destination = tmp_path / "project.json"
    original = b'{"valid": "original"}'
    destination.write_bytes(original)

    def fail_dump(_payload, file_handle, **_kwargs):
        file_handle.write('{"partial":')
        raise TypeError("not serializable")

    monkeypatch.setattr(utils.json, "dump", fail_dump)
    with pytest.raises(TypeError, match="not serializable"):
        utils.save_json(str(destination), {"invalid": object()})

    assert destination.read_bytes() == original
    assert _temporary_files(tmp_path) == []


def test_save_json_replace_failure_preserves_original_and_removes_temporary(tmp_path, monkeypatch):
    destination = tmp_path / "project.json"
    original = b'{"valid": "original"}'
    destination.write_bytes(original)

    def fail_replace(_source, _destination):
        raise PermissionError("replace denied")

    monkeypatch.setattr(utils.os, "replace", fail_replace)
    with pytest.raises(PermissionError, match="replace denied"):
        utils.save_json(str(destination), {"new": "content"})

    assert destination.read_bytes() == original
    assert _temporary_files(tmp_path) == []
