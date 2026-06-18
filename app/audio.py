from __future__ import annotations

import os
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import platform
import queue
import subprocess
import threading
import time
from typing import Optional

try:
    import pygame
except Exception:
    pygame = None

from app import config


class AudioManager:
    """Audio playback + text to speech.

    The previous implementation created one background thread per TTS request.
    That design was prone to race conditions on Windows after alternating
    between the global "Leer" action and cell-level TTS. This version uses a
    single dedicated worker queue for TTS so utterances are serialized and old
    requests cannot corrupt the state of newer ones.
    """

    def __init__(self) -> None:
        self._tts_rate = 160
        self._lock = threading.RLock()
        self._tts_process: Optional[subprocess.Popen] = None
        self._tts_generation = 0
        self._mci_alias: Optional[str] = None
        self._mci_available = platform.system().lower().startswith("win")
        self._mci = None
        if self._mci_available:
            try:
                import ctypes
                self._mci = ctypes.windll.winmm.mciSendStringW
            except Exception:
                self._mci = None
                self._mci_available = False

        self._pygame_ready = False
        self._tts_queue: queue.Queue[tuple[str, int, str | None]] = queue.Queue()
        self._tts_worker = threading.Thread(target=self._tts_worker_loop, name="sara-tts-worker", daemon=True)
        self._tts_worker.start()

    def _ensure_pygame(self) -> bool:
        if pygame is None:
            return False
        if self._pygame_ready:
            return True
        try:
            pygame.mixer.init()
            self._pygame_ready = True
            return True
        except Exception:
            self._pygame_ready = False
            return False

    def _mci_send(self, command: str) -> bool:
        if not self._mci:
            return False
        try:
            result = self._mci(command, None, 0, None)
            return int(result) == 0
        except Exception:
            return False

    def _generation_is_current(self, generation: int) -> bool:
        with self._lock:
            return generation == self._tts_generation

    def _clear_pending_tts(self) -> None:
        while True:
            try:
                self._tts_queue.get_nowait()
            except queue.Empty:
                break
            except Exception:
                break

    def stop(self) -> None:
        with self._lock:
            self._tts_generation += 1
            active_proc = self._tts_process
            self._tts_process = None
            active_alias = self._mci_alias
            self._mci_alias = None

        self._clear_pending_tts()

        try:
            if active_proc is not None and active_proc.poll() is None:
                active_proc.terminate()
                try:
                    active_proc.wait(timeout=1.0)
                except Exception:
                    try:
                        active_proc.kill()
                    except Exception:
                        pass
        except Exception:
            pass

        if active_alias:
            try:
                self._mci_send(f"stop {active_alias}")
            except Exception:
                pass
            try:
                self._mci_send(f"close {active_alias}")
            except Exception:
                pass

        try:
            if self._pygame_ready and pygame is not None:
                pygame.mixer.music.stop()
        except Exception:
            pass

        # Guard pause so Windows can release the audio endpoint cleanly before
        # the next TTS or MP3 request starts.
        time.sleep(0.08)

    def _preferred_voice_keywords(self) -> list[str]:
        lang = getattr(config, "CURRENT_UI_LANGUAGE", getattr(config, "DEFAULT_UI_LANGUAGE", "es"))
        if (lang or "es").lower() == "en":
            return ["zira", "david", "hazel", "english", "en-us", "en-gb", "409"]
        return ["helena", "sabina", "spanish", "es-es", "es-mx", "c0a", "40a"]

    def _powershell_voice_filter(self) -> str:
        parts = [kw.replace("'", "''") for kw in self._preferred_voice_keywords()]
        return " or ".join([f"$d -match '{kw}'" for kw in parts])

    def _select_best_pyttsx3_voice(self, engine) -> None:
        try:
            voices = engine.getProperty("voices")
        except Exception:
            return
        if not voices:
            return

        keywords = [kw.lower() for kw in self._preferred_voice_keywords()]

        def _voice_score(v) -> int:
            name = (getattr(v, "name", "") or "").lower()
            vid = (getattr(v, "id", "") or "").lower()
            langs = getattr(v, "languages", []) or []
            langs_str = " ".join(
                [
                    (x.decode("utf-8", errors="ignore") if isinstance(x, bytes) else str(x))
                    for x in langs
                ]
            ).lower()
            label = f"{name} {vid} {langs_str}"
            score = 0
            for kw in keywords:
                if kw in name:
                    score += 5
                if kw in vid:
                    score += 3
                if kw in langs_str:
                    score += 2
                if kw in label:
                    score += 1
            return score

        best = None
        best_score = 0
        for voice in voices:
            score = _voice_score(voice)
            if score > best_score:
                best = voice
                best_score = score
        if best is None or best_score <= 0:
            return
        try:
            engine.setProperty("voice", best.id)
        except Exception:
            pass

    def _run_powershell_tts(self, text: str, generation: int, system_speech: bool = False) -> bool:
        if not platform.system().lower().startswith("win"):
            return False
        if not self._generation_is_current(generation):
            return False

        proc: Optional[subprocess.Popen] = None
        try:
            escaped = text.replace("'", "''")
            voice_filter = self._powershell_voice_filter()
            if not system_speech:
                command = (
                    "$voice = New-Object -ComObject SAPI.SpVoice; "
                    "$voices = @($voice.GetVoices()); "
                    "$target = $null; "
                    "foreach ($v in $voices) { "
                    "  $d = ($v.GetDescription() + ' ' + $v.Id); "
                    f"  if ({voice_filter}) {{ $target = $v; break }} "
                    "}; "
                    "if ($target -ne $null) { $voice.Voice = $target }; "
                    f"[void]$voice.Speak('{escaped}')"
                )
            else:
                command = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    "$voices = @($speak.GetInstalledVoices()); "
                    "$target = $null; "
                    "foreach ($v in $voices) { "
                    "  $d = ($v.VoiceInfo.Name + ' ' + $v.VoiceInfo.Culture + ' ' + $v.VoiceInfo.Id); "
                    f"  if ({voice_filter}) {{ $target = $v; break }} "
                    "}; "
                    "if ($target -ne $null) { $speak.SelectVoice($target.VoiceInfo.Name) }; "
                    f"$speak.Rate = 0; $speak.Speak('{escaped}')"
                )
            cmd = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-STA",
                "-Command",
                command,
            ]
            startupinfo = None
            creationflags = 0
            if hasattr(subprocess, "STARTUPINFO"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags = subprocess.CREATE_NO_WINDOW

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )
            with self._lock:
                if generation != self._tts_generation:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    return False
                self._tts_process = proc
            proc.wait(timeout=60)
            return self._generation_is_current(generation) and proc.returncode == 0
        except Exception:
            return False
        finally:
            with self._lock:
                if self._tts_process is proc:
                    self._tts_process = None

    def _run_pyttsx3_tts(self, text: str, generation: int) -> bool:
        if not self._generation_is_current(generation):
            return False
        try:
            # Import pyttsx3 lazily so startup never blocks on the TTS backend.
            import pyttsx3
            engine = pyttsx3.init()
            try:
                engine.setProperty("rate", self._tts_rate)
            except Exception:
                pass
            self._select_best_pyttsx3_voice(engine)
            if not self._generation_is_current(generation):
                return False
            engine.say(text)
            engine.runAndWait()
            try:
                engine.stop()
            except Exception:
                pass
            return self._generation_is_current(generation)
        except Exception:
            return False

    def _speak_blocking(self, text: str, generation: int) -> bool:
        system_is_windows = platform.system().lower().startswith("win")
        if not self._generation_is_current(generation):
            return False
        if self._run_pyttsx3_tts(text, generation):
            return True
        if not self._generation_is_current(generation):
            return False
        if system_is_windows and self._run_powershell_tts(text, generation, system_speech=False):
            return True
        if not self._generation_is_current(generation):
            return False
        if system_is_windows and self._run_powershell_tts(text, generation, system_speech=True):
            return True
        return False

    def _tts_worker_loop(self) -> None:
        while True:
            try:
                command, generation, payload = self._tts_queue.get()
            except Exception:
                continue
            if command == "quit":
                return
            if command != "speak" or not payload:
                continue
            if not self._generation_is_current(generation):
                continue
            try:
                self._speak_blocking(payload, generation)
            except Exception:
                pass

    def speak(self, text: str) -> bool:
        text = (text or "").strip()
        if not text:
            return False
        try:
            self.stop()
            with self._lock:
                generation = self._tts_generation
            self._tts_queue.put(("speak", generation, text))
            return True
        except Exception:
            return False

    def play_file(self, path: str) -> bool:
        path = os.path.abspath((path or "").strip())
        if not path or not os.path.exists(path):
            return False
        system = platform.system().lower()
        try:
            self.stop()
            if system.startswith("win") and self._mci_available:
                alias = f"sara_audio_{int(time.time() * 1000)}"
                escaped = path.replace("\\", "\\\\").replace('"', '\\"')
                if self._mci_send(f'open "{escaped}" alias {alias}'):
                    if self._mci_send(f"play {alias}"):
                        self._mci_alias = alias
                        return True
                    self._mci_send(f"close {alias}")
            if self._ensure_pygame():
                try:
                    pygame.mixer.music.load(path)
                    pygame.mixer.music.play()
                    return True
                except Exception:
                    pass
            if system == "darwin":
                subprocess.Popen(["afplay", path])
                return True
            for cmd in (["ffplay", "-nodisp", "-autoexit", path], ["paplay", path], ["aplay", path]):
                try:
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return True
                except Exception:
                    continue
            return False
        except Exception:
            return False

    def play_or_speak(self, audio_path: str, text: str, tts_enabled: bool = True) -> str:
        if audio_path and self.play_file(audio_path):
            return "file"
        if tts_enabled and self.speak(text):
            return "tts"
        return "none"
