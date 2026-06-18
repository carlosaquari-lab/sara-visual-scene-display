from __future__ import annotations

import os
from typing import Any

from app.i18n import tr


class SessionService:
    """Coordinate user interactions, TTS/audio playback and research logging.

    This keeps repeated runtime logic out of ui_main.py so UI code can focus on
    widget updates and dialog orchestration.
    """

    def __init__(self, controller, audio, research, users_manager):
        self.controller = controller
        self.audio = audio
        self.research = research
        self.users_manager = users_manager



    @staticmethod
    def _normalize_category_value(value: str | None) -> str:
        value = "" if value is None else str(value).strip()
        if not value:
            return ""
        if value.lower() in {"none", "null", "n/a", "na", "sin", "(none)", "(ninguna)"}:
            return ""
        return value

    def _resolve_cell_metadata(self, result) -> tuple[str, str]:
        key_typology = self._normalize_category_value(getattr(result, "key_typology", ""))
        if not key_typology:
            key_typology = self._normalize_category_value(getattr(result, "fitzgerald_category", ""))
        discourse_function = self._normalize_category_value(getattr(result, "discourse_function", ""))
        return key_typology, discourse_function

    def _resolve_hotspot_vocabulary(self, result) -> tuple[str, str, str]:
        category_id = self._normalize_category_value(getattr(result, "vocabulary_category_id", ""))
        category_label = self._normalize_category_value(getattr(result, "vocabulary_category_label", ""))
        category_group = self._normalize_category_value(getattr(result, "vocabulary_category_group", ""))
        return category_id, category_label, category_group

    def layout_name(self, project) -> str:
        return os.path.basename(project.file_path) if getattr(project, "file_path", "") else "unsaved_project"

    def research_mode_name(self, current_mode: str) -> str:
        return "User" if current_mode == "user" else "Therapist"

    def build_research_context(self, project, current_scene, current_scene_index: int, current_mode: str) -> dict[str, Any]:
        return {
            "layout_file": self.layout_name(project),
            "mode": self.research_mode_name(current_mode),
            "project_title": project.project_name,
            "scene_id": str(current_scene.id),
            "scene_title": current_scene.title,
            "scene_index": current_scene_index,
            "scene_focus_category_id": getattr(current_scene, "scene_focus_category_id", None) or "",
            "scene_focus_category_label": getattr(current_scene, "scene_focus_category_label", None) or "",
            "scene_specific_topic": getattr(current_scene, "scene_specific_topic", "") or "",
        }

    def current_user_payload(self) -> dict[str, str]:
        return {
            "user_id": self.users_manager.current_user_id or "",
            "user_name": self.users_manager.get_current_user_name() or "",
        }

    def sync_research_context(self, project, current_scene, current_scene_index: int, current_mode: str) -> None:
        try:
            self.research.set_session_context(**self.build_research_context(project, current_scene, current_scene_index, current_mode))
        except Exception:
            pass

    def sync_research_text(self, text: str, mode: str = "Therapist") -> None:
        self.research.set_current_text(text, mode=mode)

    def log_layout_save(self, project, current_scene, current_scene_index: int, current_mode: str, layout_file: str | None = None) -> None:
        payload = self.build_research_context(project, current_scene, current_scene_index, current_mode)
        if layout_file:
            payload["layout_file"] = layout_file
        self.research.log_event(action="layout_save", **payload)

    def speak_output_text(self, project, current_scene, current_scene_index: int, current_mode: str, text: str) -> bool:
        text = (text or "").strip()
        if not text:
            return False
        if not self.audio.speak(text):
            return False
        payload = self.build_research_context(project, current_scene, current_scene_index, current_mode)
        self.research.log_event(
            action="key_press",
            key_raw=tr("read"),
            key_type="special",
            **payload,
        )
        self.research.log_event(
            action="tts_play",
            key_raw=tr("read"),
            key_type="special",
            audio_source="tts",
            **payload,
        )
        return True

    def backspace_output_text(self, project, current_scene, current_scene_index: int, current_mode: str, current_text: str) -> str | None:
        if not (current_text or "").strip():
            return None
        new_text = self.controller.backspace_output(current_text)
        payload = self.build_research_context(project, current_scene, current_scene_index, current_mode)
        self.research.log_event(action="key_press", key_raw=tr("delete"), key_type="special", **payload)
        return new_text

    def clear_output_text(self, project, current_scene, current_scene_index: int, current_mode: str) -> str:
        new_text = self.controller.clear_output()
        payload = self.build_research_context(project, current_scene, current_scene_index, current_mode)
        self.research.log_event(action="clear", key_raw=tr("clear"), key_type="special", **payload)
        return new_text

    def play_scene_audio(self, project, current_scene, current_scene_index: int, current_mode: str) -> str:
        payload = self.controller.scene_audio_payload()
        source = self.audio.play_or_speak(payload["audio_path"], payload["speak_text"], tts_enabled=payload["tts_enabled"])
        if source != "none":
            self.research.log_event(
                action="audio_play" if source == "file" else "tts_play",
                key_raw="scene_audio",
                key_type="scene_audio",
                audio_source=source,
                **self.build_research_context(project, current_scene, current_scene_index, current_mode),
            )
        return source

    def activate_hotspot(self, project, current_scene, current_scene_index: int, current_mode: str, hotspot, current_text: str):
        result = self.controller.activate_hotspot(hotspot, current_text)
        if result.action != "insert":
            return result

        payload = self.build_research_context(project, current_scene, current_scene_index, current_mode)
        payload.update(self.current_user_payload())
        category_id, category_label, category_group = self._resolve_hotspot_vocabulary(result)

        if result.inserted_text:
            self.users_manager.user_segment_key_presses += 1
            self.users_manager.user_segment_words_inserted += len(result.inserted_text.split())
            self.users_manager.user_segment_characters_inserted += len(result.inserted_text)
            self.research.log_event(
                action="key_press",
                key_raw=result.inserted_text,
                key_type="scene_hotspot",
                vocabulary_category_id=category_id,
                vocabulary_category_label=category_label,
                vocabulary_category_group=category_group,
                representation_type=getattr(result, "representation_type", "scene_hotspot") or "scene_hotspot",
                visual_source="scene_hotspot",
                text_inserted=result.inserted_text,
                **payload,
            )

        source = self.audio.play_or_speak(result.audio_path, result.speak_text, tts_enabled=result.tts_enabled)
        if source != "none":
            self.research.log_event(
                action="audio_play" if source == "file" else "tts_play",
                key_raw=result.inserted_text or result.speak_text,
                key_type="scene_hotspot_audio",
                vocabulary_category_id=category_id,
                vocabulary_category_label=category_label,
                vocabulary_category_group=category_group,
                representation_type=getattr(result, "representation_type", "scene_hotspot") or "scene_hotspot",
                audio_source=source,
                **payload,
            )
        return result

    def activate_cell(self, project, current_scene, current_scene_index: int, current_mode: str, index: int, current_text: str):
        result = self.controller.activate_cell(index, current_text)
        if result.action != "insert":
            return result

        key_typology, discourse_function = self._resolve_cell_metadata(result)

        if result.inserted_text:
            self.users_manager.user_segment_key_presses += 1
            self.users_manager.user_segment_words_inserted += len(result.inserted_text.split())
            self.users_manager.user_segment_characters_inserted += len(result.inserted_text)
            payload = self.build_research_context(project, current_scene, current_scene_index, current_mode)
            payload.update(self.current_user_payload())
            self.research.log_event(
                action="key_press",
                key_raw=result.inserted_text,
                key_type="visual_support",
                representation_type=getattr(result, "representation_type", "") or "",
                visual_source=getattr(result, "visual_source", "") or "",
                text_inserted=result.inserted_text,
                **payload,
            )

        source = self.audio.play_or_speak(result.audio_path, result.speak_text, tts_enabled=result.tts_enabled)
        if source != "none":
            payload = self.build_research_context(project, current_scene, current_scene_index, current_mode)
            payload.update(self.current_user_payload())
            self.research.log_event(
                action="audio_play" if source == "file" else "tts_play",
                key_raw=result.inserted_text or current_scene.cells[index].text,
                key_type="visual_support_audio",
                audio_source=source,
                **payload,
            )
        return result

    def activate_support(self, project, current_scene, current_scene_index: int, current_mode: str, index: int, current_text: str):
        """Activate a SaraB visual support stored in scene.supports.

        This is intentionally separate from activate_cell(): SaraB support
        cards are not the legacy communication grid and are serialized under
        the scene ``supports`` key.
        """
        result = self.controller.activate_support(index, current_text)
        if result.action != "insert":
            return result

        key_typology, discourse_function = self._resolve_cell_metadata(result)

        if result.inserted_text:
            self.users_manager.user_segment_key_presses += 1
            self.users_manager.user_segment_words_inserted += len(result.inserted_text.split())
            self.users_manager.user_segment_characters_inserted += len(result.inserted_text)
            payload = self.build_research_context(project, current_scene, current_scene_index, current_mode)
            payload.update(self.current_user_payload())
            self.research.log_event(
                action="key_press",
                key_raw=result.inserted_text,
                key_type="visual_support",
                representation_type=getattr(result, "representation_type", "") or "",
                visual_source=getattr(result, "visual_source", "") or "",
                text_inserted=result.inserted_text,
                **payload,
            )

        source = self.audio.play_or_speak(result.audio_path, result.speak_text, tts_enabled=result.tts_enabled)
        if source != "none":
            payload = self.build_research_context(project, current_scene, current_scene_index, current_mode)
            payload.update(self.current_user_payload())
            try:
                raw_text = current_scene.supports[index].text
            except Exception:
                raw_text = result.inserted_text
            self.research.log_event(
                action="audio_play" if source == "file" else "tts_play",
                key_raw=result.inserted_text or raw_text,
                key_type="visual_support_audio",
                audio_source=source,
                **payload,
            )
        return result

