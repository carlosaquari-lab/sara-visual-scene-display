from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.audio import AudioManager


class FakeMusic:
    def __init__(self):
        self.loaded = []
        self.play_calls = 0
        self.stop_calls = 0

    def load(self, path):
        self.loaded.append(path)

    def play(self):
        self.play_calls += 1

    def stop(self):
        self.stop_calls += 1


class FakeMixer:
    def __init__(self):
        self.music = FakeMusic()
        self.init_calls = 0

    def init(self):
        self.init_calls += 1


def test_play_file_falls_back_to_pygame_when_windows_mci_fails(monkeypatch, tmp_path):
    audio_file = tmp_path / "project – unicode" / "audio" / "recorded.wav"
    audio_file.parent.mkdir(parents=True)
    audio_file.write_bytes(b"not a real wav for mocked pygame")
    fake_mixer = FakeMixer()
    fake_pygame = SimpleNamespace(mixer=fake_mixer)
    monkeypatch.setattr("app.audio.pygame", fake_pygame)
    monkeypatch.setattr("app.audio.platform.system", lambda: "Windows")
    manager = AudioManager()
    manager._mci_available = True
    manager._mci = object()
    manager._mci_send = lambda _command: False

    assert manager.play_file(str(audio_file)) is True
    assert fake_mixer.init_calls == 1
    assert fake_mixer.music.loaded == [str(audio_file.resolve())]
    assert fake_mixer.music.play_calls == 1