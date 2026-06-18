from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import threading
import wave

from app import config


_RE_SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe_component(value: str | None, fallback: str) -> str:
    text = str(value or "").strip() or fallback
    text = _RE_SAFE_COMPONENT.sub("_", text)
    text = text.strip("._-")
    return text or fallback


def recording_timestamp(now: datetime | None = None) -> str:
    """Return a filesystem-safe timestamp for recorded audio filenames."""
    stamp = now or datetime.now()
    return stamp.strftime("%Y%m%d_%H%M%S_%f")


def recording_filename(scene_id: str | None, hotspot_id: str | None, timestamp: str | None = None) -> str:
    """Build a unique-ish WAV filename for a hotspot recording."""
    scene = _safe_component(scene_id, "scene")
    hotspot = _safe_component(hotspot_id, "hotspot")
    stamp = _safe_component(timestamp or recording_timestamp(), "recording")
    return f"hotspot_{scene}_{hotspot}_{stamp}.wav"


def project_audio_assets_dir(project_path: str | Path) -> Path:
    project = Path(project_path)
    return project.parent / f"{project.stem}_assets" / "audio"


def fallback_recordings_dir(base_audio_dir: str | Path | None = None) -> Path:
    base = Path(base_audio_dir) if base_audio_dir is not None else Path(config.AUDIO_DIR)
    return base / "recordings"


def recording_destination_dir(project_path: str | Path | None = None, *, base_audio_dir: str | Path | None = None) -> Path:
    """Choose where a new recording should be written.

    If the saved project's assets/audio folder already exists, use it. For an
    unsaved project, or for a project whose assets/audio folder has not been
    created yet, use Sara's controlled recordings folder under sarab_data/audio.
    """
    if project_path:
        assets_audio = project_audio_assets_dir(project_path)
        if assets_audio.exists() and assets_audio.is_dir():
            return assets_audio
    return fallback_recordings_dir(base_audio_dir)


def ensure_recording_dir(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def recording_path_for_hotspot(
    scene_id: str | None,
    hotspot_id: str | None,
    project_path: str | Path | None = None,
    *,
    base_audio_dir: str | Path | None = None,
    timestamp: str | None = None,
    create_dir: bool = True,
) -> Path:
    directory = recording_destination_dir(project_path, base_audio_dir=base_audio_dir)
    if create_dir:
        ensure_recording_dir(directory)
    return directory / recording_filename(scene_id, hotspot_id, timestamp)


class WavRecordingSession:
    """Start/stop microphone recording into a PCM WAV file.

    The class keeps microphone access isolated from Tkinter. Production code
    lets it import sounddevice lazily; tests can pass a fake sounddevice module.
    """

    def __init__(
        self,
        destination: str | Path,
        *,
        samplerate: int = 44100,
        channels: int = 1,
        sounddevice_module=None,
    ) -> None:
        if samplerate <= 0:
            raise ValueError("samplerate must be greater than zero")
        if channels <= 0:
            raise ValueError("channels must be greater than zero")
        self.destination = Path(destination)
        self.samplerate = int(samplerate)
        self.channels = int(channels)
        self._sounddevice = sounddevice_module
        self._stream = None
        self._wav_file = None
        self._started = False
        self._lock = threading.RLock()

    @property
    def is_recording(self) -> bool:
        return self._started

    def _get_sounddevice(self):
        if self._sounddevice is not None:
            return self._sounddevice
        import sounddevice as sd
        self._sounddevice = sd
        return sd

    def _callback(self, indata, _frames, _time_info, _status) -> None:
        with self._lock:
            if self._wav_file is None:
                return
            self._wav_file.writeframes(indata.tobytes())

    def start(self) -> Path:
        with self._lock:
            if self._started:
                return self.destination
            ensure_recording_dir(self.destination.parent)
            self._wav_file = wave.open(str(self.destination), "wb")
            self._wav_file.setnchannels(self.channels)
            self._wav_file.setsampwidth(2)
            self._wav_file.setframerate(self.samplerate)
            sd = self._get_sounddevice()
            self._stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=self.channels,
                dtype="int16",
                callback=self._callback,
            )
            self._stream.start()
            self._started = True
            return self.destination

    def stop(self) -> Path:
        with self._lock:
            stream = self._stream
            self._stream = None
            self._started = False
        try:
            if stream is not None:
                stream.stop()
                stream.close()
        finally:
            with self._lock:
                wav_file = self._wav_file
                self._wav_file = None
            if wav_file is not None:
                wav_file.close()
        return self.destination

    def cancel(self, *, remove_file: bool = True) -> None:
        path = self.destination
        self.stop()
        if remove_file:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass


def record_wav(
    destination: str | Path,
    duration_seconds: float,
    *,
    samplerate: int = 44100,
    channels: int = 1,
    sounddevice_module=None,
) -> Path:
    """Record microphone audio to a PCM WAV file for a fixed duration."""
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be greater than zero")
    if samplerate <= 0:
        raise ValueError("samplerate must be greater than zero")
    if channels <= 0:
        raise ValueError("channels must be greater than zero")

    sd = sounddevice_module
    if sd is None:
        import sounddevice as sd  # type: ignore[no-redef]

    destination = Path(destination)
    ensure_recording_dir(destination.parent)
    frames = int(float(duration_seconds) * int(samplerate))
    audio_data = sd.rec(frames, samplerate=int(samplerate), channels=int(channels), dtype="int16")
    sd.wait()

    with wave.open(str(destination), "wb") as wav_file:
        wav_file.setnchannels(int(channels))
        wav_file.setsampwidth(2)
        wav_file.setframerate(int(samplerate))
        wav_file.writeframes(audio_data.tobytes())
    return destination