import time
import csv
import hashlib
import json
from pathlib import Path
from datetime import datetime
from collections import Counter
from uuid import uuid4


from app.research_support import (
    append_csv_row,
    ensure_csv_header,
    global_log_header,
    session_events_header,
    summary_header,
    upsert_csv_row,
    write_json,
)


class ResearchLogger:
    """Research logging and session statistics for Sara.

    Main outputs:
      - per-session events CSV: events_<session_id>.csv
      - global log CSV: global_log.csv
      - session summary CSV: session_summary.csv
      - session summary JSON: session_summary_<session_id>.json

    This rebuild keeps the 3.6 behaviour but strengthens reuse for researchers:
      - richer session context (project + scene)
      - scene dwell time tracking
      - explicit audio source tracking (recorded audio vs TTS)
      - safer autosave of summaries
    """

    def __init__(
        self,
        logs_dir: str,
        schema_version: str = "12",
        ui_language: str = "en",
        app_name: str = "",
        app_version: str = "",
        author: str = "",
        **_ignored,
    ):
        self.logs_dir = Path(logs_dir)
        self.schema_version = str(schema_version)
        self.ui_language = ui_language if ui_language in {"en", "es"} else "en"
        self.app_name = app_name
        self.app_version = app_version
        self.author = author

        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.research_enabled = False
        self.research_ever_enabled = False
        self.session_id = self._new_session_id()
        self.session_start_time = time.time()
        self.session_start_mode = "Therapist"
        self.current_layout_file = "sara"
        self.current_project_title = ""
        self.current_scene_id = ""
        self.current_scene_title = ""
        self.current_scene_index = 0
        self.current_scene_focus_category_id = ""
        self.current_scene_focus_category_label = ""
        self.current_scene_specific_topic = ""
        self.support_strip_enabled = 0
        self.support_slots_total = 0
        self.support_slots_configured = 0
        self.support_slots_presented = 0
        self.current_text = ""
        self.session_type = "test"
        self.is_anonymous = True

        self.summary_autosave_interval_seconds = 5.0
        self._last_summary_write_ts = 0.0
        self._last_summary_autosave_ts = 0.0
        if self.research_enabled:
            self.research_ever_enabled = True
        self._last_event_ts = self.session_start_time
        self._scene_enter_ts = self.session_start_time
        self._research_elapsed_accumulated = 0.0
        self._research_active_started_ts = None
        self._scene_dwell_counter = Counter()
        self._visited_scenes = set()
        self._last_persistence_issue = None
        self._last_persistence_success = None

        self.session_counters = self._empty_counters()
        self.word_counter = Counter()
        self.keytype_counter = Counter()
        self.pressed_element_counter = Counter()
        self.representation_counter = Counter()
        self.visual_source_counter = Counter()
        self.key_counter = Counter()
        self.system_action_counter = Counter()
        self.vocabulary_category_counter = Counter()
        self.vocabulary_group_counter = Counter()
        self.quick_phrase_counter = Counter()
        self.audio_source_counter = Counter()

        self.global_log_path = self.logs_dir / "global_log.csv"
        self.session_summary_path = self.logs_dir / "session_summary.csv"
        self.session_events_path = self.logs_dir / f"events_{self.session_id}.csv"
        self._session_events_initialized = False
        self._session_event_count = 0
        self._participant_event_count = 0
        self._pending_toggle_on_event = None
        self._session_closed = False
        self._last_research_closed_at = ""

        # Cumulative files are created at startup because they act as indexes.
        # Per-session event files are now lazy-created only when research is
        # actually enabled and the first event is written. This avoids empty
        # events_*.csv files when the program starts, a project is loaded, or
        # technical dialogs are opened with research OFF.
        self._ensure_global_log_header()
        self._ensure_session_summary_header()

    def _ui(self, en: str, es: str) -> str:
        return es if self.ui_language == "es" else en

    def _new_session_id(self) -> str:
        """Return a collision-resistant session identifier.

        Older builds used second-level timestamps (YYYYMMDD_HHMMSS). That made
        quick ON/OFF/ON transitions reuse the same session id and could merge
        or overwrite research outputs. The readable timestamp is kept, but a
        microsecond component and short UUID suffix make the id unique in fast
        transitions.
        """
        return f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_{uuid4().hex[:8]}"

    def _empty_counters(self) -> dict:
        return {
            "total_key_presses": 0,
            "total_mouse_clicks": 0,
            "total_words_inserted": 0,
            "total_characters_inserted": 0,
            "total_tts_plays": 0,
            "total_audio_file_plays": 0,
            "total_clears": 0,
            "total_clear_all": 0,
            "total_deletes": 0,
            "total_layout_saves": 0,
            "total_layout_loads": 0,
            "total_scene_changes": 0,
            "total_support_activations": 0,
            "communication_category_count": 0,
            "turn_count": 0,
            "correct_count": 0,
            "incorrect_count": 0,
            "unmarked_count": 0,
        }

    def reset_session(self, new_mode: str | None = None, session_id: str | None = None):
        preserved_session_type = getattr(self, "session_type", "test")
        preserved_is_anonymous = bool(getattr(self, "is_anonymous", True))
        self.session_id = str(session_id) if session_id else self._new_session_id()
        self.session_events_path = self.logs_dir / f"events_{self.session_id}.csv"
        self._session_events_initialized = False
        self._session_event_count = 0
        self._participant_event_count = 0
        self._pending_toggle_on_event = None
        self._session_closed = False
        self.session_start_time = time.time()
        self._last_event_ts = self.session_start_time
        self._scene_enter_ts = self.session_start_time
        self._research_elapsed_accumulated = 0.0
        self._research_active_started_ts = self.session_start_time if self.research_enabled else None
        if new_mode is not None:
            self.session_start_mode = new_mode
        self.session_counters = self._empty_counters()
        self.current_text = ""
        self.session_type = preserved_session_type
        self.is_anonymous = preserved_is_anonymous
        self.word_counter = Counter()
        self.keytype_counter = Counter()
        self.pressed_element_counter = Counter()
        self.representation_counter = Counter()
        self.visual_source_counter = Counter()
        self.key_counter = Counter()
        self.system_action_counter = Counter()
        self.vocabulary_category_counter = Counter()
        self.vocabulary_group_counter = Counter()
        self.quick_phrase_counter = Counter()
        self.audio_source_counter = Counter()
        self._scene_dwell_counter = Counter()
        self._visited_scenes = set()
        self._last_persistence_issue = None
        self._last_persistence_success = None
        if self.current_scene_id:
            self._visited_scenes.add(self.current_scene_id)
        if self.research_enabled:
            self._pending_toggle_on_event = {
                "reason": "session_started",
                "created_ts": self.session_start_time,
            }
        self._ensure_session_files()
        self._last_summary_write_ts = 0.0
        self._last_summary_autosave_ts = 0.0

    def _ensure_session_files(self) -> None:
        self._ensure_global_log_header()
        self._ensure_session_summary_header()

    def _ensure_session_events_file(self) -> None:
        if not getattr(self, "_session_events_initialized", False):
            self._init_session_events_file()
            self._session_events_initialized = True

    def set_ui_language(self, ui_language: str) -> None:
        if ui_language in {"en", "es"}:
            self.ui_language = ui_language

    def set_research_enabled(self, enabled: bool) -> None:
        previous = bool(self.research_enabled)
        self.research_enabled = bool(enabled)
        now_ts = time.time()
        if self.research_enabled:
            self.research_ever_enabled = True
            self._session_closed = False
            if not previous:
                self._research_active_started_ts = now_ts
                self._scene_enter_ts = now_ts
                if self.current_scene_id:
                    self._visited_scenes.add(self.current_scene_id)
                    self._scene_dwell_counter.setdefault(self.current_scene_id, 0.0)
        elif previous:
            self._session_closed = True
            self._last_research_closed_at = datetime.now().isoformat(timespec="seconds")
            if self._research_active_started_ts is not None:
                self._research_elapsed_accumulated += max(0.0, now_ts - float(self._research_active_started_ts))
            self._research_active_started_ts = None
            if self.current_scene_id:
                self._register_scene_dwell(now_ts)
            self._scene_enter_ts = now_ts

    def set_enabled(self, enabled: bool, silent: bool = True) -> None:
        self.set_research_enabled(enabled)

    def set_participant_context(self, session_type: str = "test", is_anonymous: bool = True) -> None:
        normalized = str(session_type or "test").strip().lower()
        if normalized not in {"participant", "test"}:
            normalized = "test"
        self.session_type = normalized
        self.is_anonymous = bool(is_anonymous)

    def get_participant_context(self) -> dict:
        return {
            "session_type": self.session_type,
            "is_anonymous": bool(self.is_anonymous),
        }

    def _sanitize_identity(self, user_id: str = "", user_name: str = "") -> tuple[str, str]:
        """Return identifiers safe for internal logging according to the session policy."""
        safe_user_id = "" if user_id is None else str(user_id)
        safe_user_name = "" if user_name is None else str(user_name)
        if bool(self.is_anonymous) or str(self.session_type).strip().lower() == "test":
            safe_user_id = ""
            safe_user_name = ""
        return safe_user_id, safe_user_name

    def _should_redact_free_text(self) -> bool:
        """Hide free-text content in anonymous/test sessions while preserving aggregate metrics."""
        return bool(self.is_anonymous) or str(self.session_type).strip().lower() == "test"

    def _sanitize_free_text(self, value: str = "") -> str:
        if self._should_redact_free_text():
            return ""
        return "" if value is None else str(value)

    def _register_scene_dwell(self, now_ts: float | None = None) -> None:
        if not self.current_scene_id:
            return
        now_ts = time.time() if now_ts is None else float(now_ts)
        elapsed = max(0.0, now_ts - float(self._scene_enter_ts or now_ts))
        self._scene_dwell_counter.setdefault(self.current_scene_id, 0.0)
        if elapsed > 0:
            self._scene_dwell_counter[self.current_scene_id] += round(elapsed, 3)
        self._scene_enter_ts = now_ts
        self._visited_scenes.add(self.current_scene_id)

    def _scene_dwell_snapshot(self) -> dict[str, float]:
        scene_ids = set(self._visited_scenes)
        if self.current_scene_id:
            scene_ids.add(self.current_scene_id)
        scene_ids.update(self._scene_dwell_counter.keys())
        snapshot: dict[str, float] = {}
        for scene_id in scene_ids:
            try:
                value = float(self._scene_dwell_counter.get(scene_id, 0.0))
            except Exception:
                value = 0.0
            snapshot[str(scene_id)] = round(max(0.0, value), 3)
        return snapshot

    def set_session_context(
        self,
        mode: str | None = None,
        layout_file: str | None = None,
        project_title: str | None = None,
        scene_id: str | None = None,
        scene_title: str | None = None,
        scene_index: int | None = None,
        scene_focus_category_id: str | None = None,
        scene_focus_category_label: str | None = None,
        scene_specific_topic: str | None = None,
    ) -> None:
        if mode:
            self.session_start_mode = mode
        if layout_file:
            self.current_layout_file = layout_file
        if project_title is not None:
            self.current_project_title = project_title

        previous_scene = self.current_scene_id
        scene_changed = scene_id is not None and str(scene_id) != str(previous_scene)
        if scene_changed and previous_scene:
            if self.research_enabled:
                self._register_scene_dwell()
                self.session_counters["total_scene_changes"] += 1
            else:
                self._scene_enter_ts = time.time()
        if scene_id is not None:
            self.current_scene_id = str(scene_id)
            self._visited_scenes.add(self.current_scene_id)
            self._scene_dwell_counter.setdefault(self.current_scene_id, 0.0)
        if scene_title is not None:
            self.current_scene_title = str(scene_title)
        if scene_index is not None:
            try:
                self.current_scene_index = int(scene_index)
            except Exception:
                self.current_scene_index = 0
        if scene_focus_category_id is not None:
            self.current_scene_focus_category_id = str(scene_focus_category_id or "")
        if scene_focus_category_label is not None:
            self.current_scene_focus_category_label = str(scene_focus_category_label or "")
        if scene_specific_topic is not None:
            self.current_scene_specific_topic = str(scene_specific_topic or "")
        if scene_changed:
            self._scene_enter_ts = time.time()

    def set_support_context(
        self,
        support_strip_enabled: int | bool = 0,
        support_slots_total: int = 0,
        support_slots_configured: int = 0,
        support_slots_presented: int = 0,
    ) -> None:
        """Store automatic support-strip context for logs and summaries.

        These fields are quantitative UI-state variables: whether the support
        strip is enabled, how many slots exist, how many have configured
        content, and how many are currently marked/presented as visible. They
        do not require external coding or clinical judgement.
        """
        try:
            self.support_strip_enabled = int(bool(support_strip_enabled))
            self.support_slots_total = int(max(0, support_slots_total or 0))
            self.support_slots_configured = int(max(0, support_slots_configured or 0))
            self.support_slots_presented = int(max(0, support_slots_presented or 0))
        except Exception:
            self.support_strip_enabled = 0
            self.support_slots_total = 0
            self.support_slots_configured = 0
            self.support_slots_presented = 0

    def set_current_text(self, text: str, mode: str | None = None) -> None:
        try:
            if mode is not None and str(mode) != "Therapist":
                self.current_text = ""
                return
            self.current_text = "" if text is None else str(text)
        except Exception:
            self.current_text = ""

    def get_current_text(self) -> str:
        try:
            return "" if self.current_text is None else str(self.current_text)
        except Exception:
            return ""

    def get_session_elapsed_seconds(self) -> float:
        """Return total elapsed time with research enabled only."""
        try:
            if not (self.research_enabled or self.research_ever_enabled):
                return 0.0
            total = float(self._research_elapsed_accumulated)
            if self.research_enabled and self._research_active_started_ts is not None:
                total += max(0.0, time.time() - float(self._research_active_started_ts))
            return round(max(0.0, total), 3)
        except Exception:
            return 0.0


    def has_activity(self) -> bool:
        """Return True only when there is meaningful participant/use activity.

        Research ON/OFF audit events, layout loads/saves and other purely
        technical events should not create a session summary by themselves.
        This keeps the logs folder understandable and avoids empty or
        misleading research outputs.
        """
        if int(getattr(self, "_participant_event_count", 0)) > 0:
            return True
        participant_counter_keys = {
            "total_key_presses",
            "total_mouse_clicks",
            "total_words_inserted",
            "total_characters_inserted",
            "total_tts_plays",
            "total_audio_file_plays",
            "total_clears",
            "total_clear_all",
            "total_deletes",
            "total_scene_changes",
        }
        if any(self.session_counters.get(k, 0) for k in participant_counter_keys):
            return True
        return bool(
            self.word_counter
            or self.key_counter
            or self.vocabulary_category_counter
            or self.vocabulary_group_counter
            or self.audio_source_counter
            or self.representation_counter
            or self.pressed_element_counter
        )

    @staticmethod
    def _is_participant_event(action: str, key_type: str = "") -> bool:
        """Identify events that represent actual use, not technical setup."""
        normalized_action = str(action or "").strip().lower()
        normalized_type = str(key_type or "").strip().lower()
        if normalized_action in {"key_press", "physical_key", "mouse_click", "clear", "tts_play", "audio_play", "response_mark_annotation", "image_response_click"}:
            return True
        if normalized_type in {"story_cell", "story_cell_audio", "visual_support", "visual_support_audio", "scene_hotspot", "scene_hotspot_audio", "scene_audio", "quick_phrase"}:
            return True
        return False

    def start_new_session(self, reason: str = "manual", write_previous: bool = False) -> None:
        if write_previous:
            try:
                self.write_session_summary(user_id="", user_name="", reason=reason)
            except Exception as exc:
                self._record_persistence_issue("start_new_session_previous_summary", exc)
        # reset_session is the only place where a new session id and its
        # events file are created. This keeps session_id and session_events_path
        # synchronized.
        self.reset_session(new_mode=self.session_start_mode)

    def log_research_toggle(self, action: str, user_id: str = "", user_name: str = "", reason: str = "") -> None:
        """Persist an explicit audit event for research ON/OFF transitions.

        ON is kept pending until the first real participant/use event. This
        prevents an isolated click on ON from creating a separate events_*.csv
        and summary for an empty technical session. OFF is written only if the
        session already contains participant activity.
        """
        normalized_action = str(action or "").strip().lower()
        if normalized_action == "toggle_research_on":
            self._pending_toggle_on_event = {
                "reason": reason or "enable_research",
                "user_id": user_id or "",
                "user_name": user_name or "",
                "created_ts": time.time(),
            }
            return
        if normalized_action == "toggle_research_off" and not self.has_activity():
            self._pending_toggle_on_event = None
            return
        self.log_event(
            action=action,
            key_raw=reason or action,
            key_type="research_toggle",
            user_id=user_id,
            user_name=user_name,
            project_title=self.current_project_title,
            layout_file=self.current_layout_file,
            mode=self.session_start_mode,
            scene_id=self.current_scene_id,
            scene_title=self.current_scene_title,
            scene_index=self.current_scene_index,
        )



    @staticmethod
    def _normalize_category_value(value: str | None) -> str:
        value = "" if value is None else str(value).strip()
        if not value:
            return ""
        if value.lower() in {"none", "null", "n/a", "na", "sin", "(none)", "(ninguna)"}:
            return ""
        return value

    @staticmethod
    def _pressed_element_bucket(action: str, key_type: str) -> str:
        normalized_action = str(action or "").strip().lower()
        normalized_type = str(key_type or "").strip().lower()
        if normalized_action == "clear" or normalized_type == "special":
            return "system_action"
        if normalized_type == "quick_phrase":
            return "quick_phrase"
        if normalized_type in {"story_cell", "story_cell_audio", "visual_support", "visual_support_audio", "scene_hotspot", "scene_hotspot_audio"}:
            return "communicative_cell"
        if normalized_type == "scene_audio":
            return "scene_audio"
        if normalized_action == "physical_key":
            return "physical_keyboard"
        if normalized_action in {"key_press", "mouse_click", "image_response_click"}:
            return "other_input"
        return ""

    @staticmethod
    def _normalize_representation_type(value: str | None) -> str:
        value = (value or "").strip().lower()
        allowed = {"text_only", "image_only", "pictogram_only", "text_image", "text_pictogram", "mixed", "scene_hotspot", "other"}
        return value if value in allowed else ""

    @staticmethod
    def _normalize_visual_source(value: str | None) -> str:
        value = (value or "").strip().lower()
        allowed = {"none", "local_image", "arasaac", "other"}
        return value if value in allowed else ""

    @staticmethod
    def _normalize_response_mark(value: str | None) -> str:
        value = (value or "").strip().lower()
        allowed = {"unmarked", "turn", "correct", "incorrect"}
        return value if value in allowed else ""

    @staticmethod
    def _normalize_annotation_source(value: str | None) -> str:
        value = (value or "").strip().lower()
        allowed = {"keyboard", "button"}
        return value if value in allowed else ""

    @staticmethod
    def _normalize_system_key(value: str | None) -> str:
        raw = "" if value is None else str(value).strip()
        normalized = raw.upper()
        aliases = {
            "BORRAR": "DELETE",
            "ELIMINAR": "DELETE",
            "PAPELERA": "CLEAR",
            "LIMPIAR": "CLEAR",
        }
        return aliases.get(normalized, normalized)

    def _summary_header(self) -> list[str]:
        return summary_header(self._empty_counters().keys())

    def _record_persistence_issue(self, stage: str, exc: Exception) -> None:
        self._last_persistence_issue = {
            "stage": str(stage),
            "error_type": exc.__class__.__name__,
            "message": str(exc),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "session_id": self.session_id,
        }

    def _record_persistence_success(self, stage: str, path: str | Path | None = None) -> None:
        self._last_persistence_success = {
            "stage": str(stage),
            "path": "" if path is None else str(path),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "session_id": self.session_id,
        }
        self._last_persistence_issue = None

    def _ensure_session_summary_header(self) -> None:
        ensure_csv_header(self.session_summary_path, self._summary_header())

    def _ensure_global_log_header(self) -> None:
        ensure_csv_header(self.global_log_path, global_log_header())

    def _init_session_events_file(self) -> None:
        ensure_csv_header(self.session_events_path, session_events_header())

    def log_event(
        self,
        action: str,
        key_raw: str = "",
        key_type: str = "",
        vocabulary_category_id: str = "",
        vocabulary_category_label: str = "",
        vocabulary_category_group: str = "",
        representation_type: str = "",
        visual_source: str = "",
        input_type: str = "",
        cursor_position: str = "",
        text_inserted: str = "",
        layout_file: str = "",
        mode: str = "",
        user_id: str = "",
        user_name: str = "",
        project_title: str = "",
        event_id: str = "",
        scene_id: str = "",
        scene_title: str = "",
        scene_index: int | str | None = None,
        scene_focus_category_id: str = "",
        scene_focus_category_label: str = "",
        scene_specific_topic: str = "",
        audio_source: str = "",
        hotspot_id: str = "",
        hotspot_label: str = "",
        click_x: str | int | float = "",
        click_y: str | int | float = "",
        x_norm: str | int | float = "",
        y_norm: str | int | float = "",
        annotated_event_id: str = "",
        response_mark: str = "",
        annotation_source: str = "",
        **_extra,
    ) -> None:
        ts = datetime.now().isoformat(timespec="seconds")
        now_ts = time.time()
        elapsed_seconds = self.get_session_elapsed_seconds()

        if layout_file:
            self.current_layout_file = layout_file
        if mode:
            self.session_start_mode = mode
        if project_title:
            self.current_project_title = project_title
        if scene_id:
            if str(scene_id) != str(self.current_scene_id):
                self.set_session_context(scene_id=str(scene_id), scene_title=scene_title or self.current_scene_title, scene_index=scene_index if scene_index is not None else self.current_scene_index)
            else:
                self.current_scene_id = str(scene_id)
        if scene_title:
            self.current_scene_title = str(scene_title)
        if scene_index is not None:
            try:
                self.current_scene_index = int(scene_index)
            except Exception:
                pass
        if scene_focus_category_id != "":
            self.current_scene_focus_category_id = str(scene_focus_category_id or "")
        if scene_focus_category_label != "":
            self.current_scene_focus_category_label = str(scene_focus_category_label or "")
        if scene_specific_topic != "":
            self.current_scene_specific_topic = str(scene_specific_topic or "")

        vocabulary_category_id = self._normalize_category_value(vocabulary_category_id)
        vocabulary_category_label = self._normalize_category_value(vocabulary_category_label)
        vocabulary_category_group = self._normalize_category_value(vocabulary_category_group)
        representation_type = self._normalize_representation_type(representation_type)
        visual_source = self._normalize_visual_source(visual_source)
        event_id = "" if event_id is None else str(event_id).strip()
        hotspot_id = "" if hotspot_id is None else str(hotspot_id).strip()
        hotspot_label = "" if hotspot_label is None else str(hotspot_label).strip()
        click_x = "" if click_x is None else str(click_x).strip()
        click_y = "" if click_y is None else str(click_y).strip()
        x_norm = "" if x_norm is None else str(x_norm).strip()
        y_norm = "" if y_norm is None else str(y_norm).strip()
        annotated_event_id = "" if annotated_event_id is None else str(annotated_event_id).strip()
        response_mark = self._normalize_response_mark(response_mark)
        annotation_source = self._normalize_annotation_source(annotation_source)

        safe_user_id, safe_user_name = self._sanitize_identity(user_id, user_name)
        safe_text_inserted = self._sanitize_free_text(text_inserted)
        is_participant_event = self._is_participant_event(action, key_type)
        is_research_toggle = str(action or "").strip().lower() in {"toggle_research_on", "toggle_research_off"}

        if self.research_enabled:
            if (not is_participant_event) and (not is_research_toggle):
                # Technical setup events such as layout_load are ignored in the
                # per-session and global research logs. They are contextual
                # actions, not participant data.
                return
            if is_participant_event and getattr(self, "_pending_toggle_on_event", None):
                pending = self._pending_toggle_on_event or {}
                self._pending_toggle_on_event = None
                self._ensure_session_events_file()
                pending_user_id, pending_user_name = self._sanitize_identity(
                    pending.get("user_id", user_id),
                    pending.get("user_name", user_name),
                )
                pending_row = [
                    datetime.fromtimestamp(float(pending.get("created_ts") or self.session_start_time)).isoformat(timespec="seconds"),
                    self.session_id,
                    self.schema_version,
                    self.current_project_title,
                    "",
                    "toggle_research_on",
                    pending.get("reason", "enable_research"),
                    "research_toggle",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    self.current_layout_file,
                    self.session_start_mode,
                    self.current_scene_id,
                    self.current_scene_title,
                    self.current_scene_index,
                    self.current_scene_focus_category_id,
                    self.current_scene_focus_category_label,
                    self.current_scene_specific_topic,
                    "",
                    0.0,
                    self.session_type,
                    int(self.is_anonymous),
                    int(getattr(self, "support_strip_enabled", 0)),
                    int(getattr(self, "support_slots_total", 0)),
                    int(getattr(self, "support_slots_configured", 0)),
                    int(getattr(self, "support_slots_presented", 0)),
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
                append_csv_row(self.session_events_path, pending_row)
                append_csv_row(self.global_log_path, pending_row + [pending_user_id, pending_user_name])
                self._session_event_count = int(getattr(self, "_session_event_count", 0)) + 1

            self._ensure_session_events_file()
            event_row = [
                ts,
                self.session_id,
                self.schema_version,
                self.current_project_title,
                event_id,
                action,
                key_raw,
                key_type,
                vocabulary_category_id,
                vocabulary_category_label,
                vocabulary_category_group,
                representation_type,
                visual_source,
                safe_text_inserted,
                self.current_layout_file,
                self.session_start_mode,
                self.current_scene_id,
                self.current_scene_title,
                self.current_scene_index,
                self.current_scene_focus_category_id if scene_focus_category_id == "" else str(scene_focus_category_id or ""),
                self.current_scene_focus_category_label if scene_focus_category_label == "" else str(scene_focus_category_label or ""),
                self.current_scene_specific_topic if scene_specific_topic == "" else str(scene_specific_topic or ""),
                audio_source,
                elapsed_seconds,
                self.session_type,
                int(self.is_anonymous),
                int(getattr(self, "support_strip_enabled", 0)),
                int(getattr(self, "support_slots_total", 0)),
                int(getattr(self, "support_slots_configured", 0)),
                int(getattr(self, "support_slots_presented", 0)),
                hotspot_id,
                hotspot_label,
                click_x,
                click_y,
                x_norm,
                y_norm,
                annotated_event_id,
                response_mark,
                annotation_source,
            ]
            append_csv_row(self.session_events_path, event_row)
            append_csv_row(
                self.global_log_path,
                event_row + [safe_user_id, safe_user_name],
            )
            self._session_event_count = int(getattr(self, "_session_event_count", 0)) + 1
            if is_participant_event:
                self._participant_event_count = int(getattr(self, "_participant_event_count", 0)) + 1

        if self.research_enabled:
            pressed_bucket = ""
            if action in {"key_press", "physical_key", "clear", "mouse_click", "image_response_click"}:
                pressed_bucket = self._pressed_element_bucket(action, key_type)
            if pressed_bucket:
                self.pressed_element_counter[pressed_bucket] += 1

            if action in {"key_press", "physical_key"}:
                self.session_counters["total_key_presses"] += 1
                if str(key_type).strip().lower() == "visual_support":
                    self.session_counters["total_support_activations"] += 1
                normalized_key = "" if key_raw is None else str(key_raw).strip()
                normalized_key_upper = normalized_key.upper()
                is_special_key = str(key_type).strip().lower() == "special"
                if normalized_key:
                    target_counter = self.system_action_counter if is_special_key else self.key_counter
                    target_counter[normalized_key] += 1
                stable_system_key = self._normalize_system_key(normalized_key_upper)
                if stable_system_key in {"⌫", "BACKSPACE", "DELETE"}:
                    self.session_counters["total_deletes"] += 1
                if stable_system_key == "CLEAR":
                    self.session_counters["total_clears"] += 1
                    self.session_counters["total_clear_all"] += 1
            elif action == "mouse_click":
                self.session_counters["total_mouse_clicks"] += 1
            elif action == "image_response_click":
                self.session_counters["total_mouse_clicks"] += 1
            elif action == "tts_play":
                self.session_counters["total_tts_plays"] += 1
                self.audio_source_counter["tts"] += 1
            elif action == "audio_play":
                self.session_counters["total_audio_file_plays"] += 1
                self.audio_source_counter["file"] += 1
            elif action == "clear":
                if key_raw:
                    self.system_action_counter[str(key_raw).strip()] += 1
                self.session_counters["total_clears"] += 1
            elif action == "response_mark_annotation":
                counter_key = f"{response_mark or 'unmarked'}_count"
                if counter_key in self.session_counters:
                    self.session_counters[counter_key] += 1
                self.session_counters["total_clear_all"] += 1
            elif action == "layout_save":
                self.session_counters["total_layout_saves"] += 1
            elif action == "layout_load":
                self.session_counters["total_layout_loads"] += 1

            if action == "key_press" and text_inserted:
                self.session_counters["total_characters_inserted"] += len(text_inserted)
                tokens = []
                for raw in str(text_inserted).lower().split():
                    tok = "".join(ch for ch in raw if ch.isalnum())
                    if len(tok) >= 2:
                        tokens.append(tok)
                self.session_counters["total_words_inserted"] += len(tokens)
                for tok in tokens:
                    self.word_counter[tok] += 1
                if vocabulary_category_id:
                    self.vocabulary_category_counter[str(vocabulary_category_id)] += 1
                if vocabulary_category_group:
                    self.vocabulary_group_counter[str(vocabulary_category_group)] += 1
                    self.session_counters["communication_category_count"] += 1
                if representation_type:
                    self.representation_counter[str(representation_type)] += 1
                if visual_source and visual_source != "none":
                    self.visual_source_counter[str(visual_source)] += 1

            if key_type:
                self.keytype_counter[key_type] += 1
                if key_type == "quick_phrase" and key_raw:
                    self.quick_phrase_counter[str(key_raw)] += 1

            last_ts = getattr(self, "_last_summary_autosave_ts", None)
            if last_ts is None:
                last_ts = getattr(self, "_last_summary_write_ts", 0.0)
            if self.has_activity() and now_ts - float(last_ts) >= float(self.summary_autosave_interval_seconds):
                self._last_summary_write_ts = now_ts
                self._last_summary_autosave_ts = now_ts
                try:
                    self.write_session_summary(mode=self.session_start_mode, layout_file=self.current_layout_file, user_id=safe_user_id, user_name=safe_user_name, reason="autosave")
                except Exception as exc:
                    self._record_persistence_issue("autosave_summary", exc)

    def toggle_logging(self) -> dict:
        """Backward-compatible toggle used by older UI code.

        This now follows the same state-machine rules as the main workflow:
        create a fresh session on ON, write explicit toggle events, and persist
        the OFF state after disabling.
        """
        enabling = not bool(self.research_enabled)
        try:
            if enabling:
                self.start_new_session(reason="enable_research", write_previous=False)
                self.set_research_enabled(True)
                self.log_research_toggle("toggle_research_on", reason="enable_research")
            else:
                self.log_research_toggle("toggle_research_off", reason="disable_research")
                self.set_research_enabled(False)
                self.flush_session_if_needed(reason="disable_research")
        except Exception as exc:
            self._record_persistence_issue("toggle_logging", exc)
        return {
            "enabled": bool(self.research_enabled),
            "title": self._ui("Research", "Investigación"),
            "message": self._ui("Research logging ENABLED.", "Registro de investigación ACTIVADO.") if self.research_enabled else self._ui("Research logging DISABLED.", "Registro de investigación DESACTIVADO."),
        }

    def flush_session_if_needed(self, user_id: str = "", user_name: str = "", reason: str = "") -> str | None:
        if not self.has_activity():
            return None
        if not (self.research_enabled or self.research_ever_enabled):
            return None
        try:
            return self.write_session_summary(user_id=user_id, user_name=user_name, reason=reason)
        except Exception as exc:
            self._record_persistence_issue("flush_session", exc)
            return None

    def force_write_summary(self, user_id: str = "", user_name: str = "") -> dict:
        if not self.has_activity():
            return {
                "saved": False,
                "reason": "no_activity",
                "title": self._ui("Research", "Investigación"),
                "message": self._ui(
                    "No session summary was saved because there is no session activity.",
                    "No se guardó ningún resumen de sesión porque no hay actividad en la sesión.",
                ),
                "path": None,
                "csv_path": None,
            }
        if not self.research_ever_enabled:
            return {
                "saved": False,
                "reason": "research_not_enabled",
                "title": self._ui("Research", "Investigación"),
                "message": self._ui(
                    "No research summary was saved because research was not enabled during this session.",
                    "No se guardó ningún resumen de investigación porque la investigación no estuvo activada durante esta sesión.",
                ),
                "path": None,
                "csv_path": None,
            }
        try:
            json_path = self.write_session_summary(user_id=user_id, user_name=user_name, reason="manual")
        except Exception as exc:
            self._record_persistence_issue("manual_summary", exc)
            return {
                "saved": False,
                "reason": "write_error",
                "title": self._ui("Research", "Investigación"),
                "message": self._ui(
                    f"The session summary could not be written.\nError: {exc}",
                    f"No se pudo guardar el resumen de sesión.\nError: {exc}",
                ),
                "path": None,
                "csv_path": None,
            }
        csv_path = self.session_summary_path
        return {
            "saved": True,
            "reason": "manual",
            "title": self._ui("Research", "Investigación"),
            "message": self._ui(
                f"Session summary written.\nCSV: {csv_path}\nJSON: {json_path}",
                f"Resumen de sesión guardado.\nCSV: {csv_path}\nJSON: {json_path}",
            ),
            "path": json_path,
            "csv_path": csv_path,
        }

    def _scene_metadata_snapshot(self) -> list[dict]:
        scenes: dict[str, dict] = {}
        ordered_keys: list[str] = []
        if self.session_events_path.exists():
            try:
                with open(self.session_events_path, "r", encoding="utf-8", newline="") as fh:
                    for row in csv.DictReader(fh):
                        scene_key = str(row.get("scene_id") or row.get("scene_title") or "").strip()
                        if not scene_key:
                            continue
                        if scene_key not in scenes:
                            ordered_keys.append(scene_key)
                            scenes[scene_key] = {
                                "scene_id": str(row.get("scene_id") or "").strip(),
                                "scene_title": str(row.get("scene_title") or "").strip(),
                                "scene_index": str(row.get("scene_index") or "").strip(),
                                "scene_focus_category_id": str(row.get("scene_focus_category_id") or "").strip(),
                                "scene_focus_category_label": str(row.get("scene_focus_category_label") or "").strip(),
                                "scene_specific_topic": str(row.get("scene_specific_topic") or "").strip(),
                            }
                        scene = scenes[scene_key]
                        for field in (
                            "scene_id",
                            "scene_title",
                            "scene_index",
                            "scene_focus_category_id",
                            "scene_focus_category_label",
                            "scene_specific_topic",
                        ):
                            if not scene.get(field):
                                scene[field] = str(row.get(field) or "").strip()
            except Exception:
                pass

        current_key = str(self.current_scene_id or self.current_scene_title or "").strip()
        if current_key and current_key not in scenes:
            ordered_keys.append(current_key)
            scenes[current_key] = {
                "scene_id": self.current_scene_id,
                "scene_title": self.current_scene_title,
                "scene_index": self.current_scene_index,
                "scene_focus_category_id": self.current_scene_focus_category_id,
                "scene_focus_category_label": self.current_scene_focus_category_label,
                "scene_specific_topic": self.current_scene_specific_topic,
            }
        return [scenes[key] for key in ordered_keys]

    def _build_session_summary_artifacts(self, user_id: str = "", user_name: str = "", reason: str = "", mode: str = "", layout_file: str = "") -> tuple[list[object], dict, Path]:
        safe_user_id, safe_user_name = self._sanitize_identity(user_id, user_name)
        if mode:
            self.session_start_mode = mode
        if layout_file:
            self.current_layout_file = layout_file
        now = datetime.now().isoformat(timespec="seconds")
        now_ts = time.time()
        self._register_scene_dwell(now_ts)
        duration = self.get_session_elapsed_seconds()

        raw_final_text = self.get_current_text()
        final_text = self._sanitize_free_text(raw_final_text)
        final_text_len_chars = len(final_text)
        final_text_len_tokens = len([t for t in str(final_text).split() if t])
        scene_dwell_snapshot = self._scene_dwell_snapshot()
        unique_scenes_visited = len(scene_dwell_snapshot)

        row = [
            now,
            self.session_id,
            self.schema_version,
            self.current_project_title,
            duration,
            self.session_start_mode,
            self.current_layout_file,
            int(self.research_enabled),
            self.session_type,
            int(self.is_anonymous),
            safe_user_id,
            safe_user_name,
            final_text,
            final_text_len_chars,
            final_text_len_tokens,
            unique_scenes_visited,
            self.session_counters.get("total_scene_changes", 0),
            int(getattr(self, "support_strip_enabled", 0)),
            int(getattr(self, "support_slots_total", 0)),
            int(getattr(self, "support_slots_configured", 0)),
            int(getattr(self, "support_slots_presented", 0)),
            *[self.session_counters[k] for k in self._empty_counters().keys()],
        ]
        json_path = self.logs_dir / f"session_summary_{self.session_id}.json"
        top_words = [] if self._should_redact_free_text() else self.word_counter.most_common(50)
        top_keys = [] if self._should_redact_free_text() else self.key_counter.most_common(50)
        payload = {
            "timestamp": now,
            "session_id": self.session_id,
            "schema_version": self.schema_version,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "author": self.author,
            "project_title": self.current_project_title,
            "duration_seconds": duration,
            "mode": self.session_start_mode,
            "layout_file": self.current_layout_file,
            "research_enabled": self.research_enabled,
            "research_ever_enabled": bool(self.research_ever_enabled),
            "session_type": self.session_type,
            "is_anonymous": bool(self.is_anonymous),
            "user_id": safe_user_id,
            "user_name": safe_user_name,
            "reason": reason,
            "current_scene": {
                "scene_id": self.current_scene_id,
                "scene_title": self.current_scene_title,
                "scene_index": self.current_scene_index,
                "scene_focus_category_id": self.current_scene_focus_category_id,
                "scene_focus_category_label": self.current_scene_focus_category_label,
                "scene_specific_topic": self.current_scene_specific_topic,
            },
            "current_scene_focus_category_id": self.current_scene_focus_category_id,
            "current_scene_focus_category_label": self.current_scene_focus_category_label,
            "current_scene_specific_topic": self.current_scene_specific_topic,
            "scene_metadata": self._scene_metadata_snapshot(),
            "support_context": {
                "support_strip_enabled": int(getattr(self, "support_strip_enabled", 0)),
                "support_slots_total": int(getattr(self, "support_slots_total", 0)),
                "support_slots_configured": int(getattr(self, "support_slots_configured", 0)),
                "support_slots_presented": int(getattr(self, "support_slots_presented", 0)),
            },
            "final_text": final_text,
            "final_text_len_chars": final_text_len_chars,
            "final_text_len_tokens": final_text_len_tokens,
            "unique_scenes_visited": unique_scenes_visited,
            "scene_dwell_seconds": scene_dwell_snapshot,
            "counters": dict(self.session_counters),
            "audio_sources": dict(self.audio_source_counter),
            "top_words": top_words,
            "top_quick_phrases": self.quick_phrase_counter.most_common(50),
            "top_keys": top_keys,
            "top_system_actions": self.system_action_counter.most_common(50),
            "top_pressed_elements": self.pressed_element_counter.most_common(50),
            "top_representation_types": self.representation_counter.most_common(50),
            "top_visual_sources": self.visual_source_counter.most_common(50),
            "category_counts": dict(self.vocabulary_category_counter),
            "communication_category_count": int(self.session_counters.get("communication_category_count", 0)),
            "top_vocabulary_categories": [category for category, _count in self.vocabulary_category_counter.most_common(50)],
            "response_mark_counts": {
                "unmarked": int(self.session_counters.get("unmarked_count", 0)),
                "turn": int(self.session_counters.get("turn_count", 0)),
                "correct": int(self.session_counters.get("correct_count", 0)),
                "incorrect": int(self.session_counters.get("incorrect_count", 0)),
            },
        }
        return row, payload, json_path

    def _write_session_summary_csv(self, row: list[object]) -> None:
        upsert_csv_row(
            self.session_summary_path,
            key_index=1,
            key_value=self.session_id,
            row=row,
            header=self._summary_header(),
        )
        self._record_persistence_success("session_summary_csv", self.session_summary_path)

    def _write_session_summary_json_file(self, json_path: Path, payload: dict) -> str:
        write_json(json_path, payload)
        self._record_persistence_success("session_summary_json", json_path)
        return str(json_path)

    def write_session_summary(self, user_id: str = "", user_name: str = "", reason: str = "", mode: str = "", layout_file: str = "") -> str:
        row, payload, json_path = self._build_session_summary_artifacts(
            user_id=user_id,
            user_name=user_name,
            reason=reason,
            mode=mode,
            layout_file=layout_file,
        )
        self._write_session_summary_csv(row)
        return self._write_session_summary_json_file(json_path, payload)

    def write_session_summary_json(self, mode: str = "", layout_file: str = "", user_id: str = "", user_name: str = "") -> str:
        _row, payload, json_path = self._build_session_summary_artifacts(
            mode=mode,
            layout_file=layout_file,
            user_id=user_id,
            user_name=user_name,
            reason="autosave",
        )
        return self._write_session_summary_json_file(json_path, payload)

    def get_status_snapshot(self, user_id: str = "", user_name: str = "") -> dict:
        safe_user_id, safe_user_name = self._sanitize_identity(user_id, user_name)
        return {
            "research_enabled": bool(self.research_enabled),
            "research_ever_enabled": bool(self.research_ever_enabled),
            "session_id": self.session_id,
            "schema_version": self.schema_version,
            "mode": self.session_start_mode,
            "layout_file": self.current_layout_file,
            "project_title": self.current_project_title,
            "scene_id": self.current_scene_id,
            "scene_title": self.current_scene_title,
            "scene_index": self.current_scene_index,
            "scene_focus_category_id": self.current_scene_focus_category_id,
            "scene_focus_category_label": self.current_scene_focus_category_label,
            "scene_specific_topic": self.current_scene_specific_topic,
            "logs_dir": self.logs_dir,
            "global_log_path": self.global_log_path,
            "session_summary_path": self.session_summary_path,
            "session_events_path": self.session_events_path,
            "global_log_exists": self.global_log_path.exists(),
            "session_summary_exists": self.session_summary_path.exists(),
            "session_events_exists": self.session_events_path.exists(),
            "session_events_filename_matches_session_id": self.session_events_path.name == f"events_{self.session_id}.csv",
            "session_events_initialized": bool(getattr(self, "_session_events_initialized", False)),
            "session_event_count": int(getattr(self, "_session_event_count", 0)),
            "participant_event_count": int(getattr(self, "_participant_event_count", 0)),
            "pending_toggle_on": bool(getattr(self, "_pending_toggle_on_event", None)),
            "session_closed": bool(getattr(self, "_session_closed", False)),
            "last_research_closed_at": getattr(self, "_last_research_closed_at", ""),
            "research_active_started_ts": self._research_active_started_ts,
            "research_elapsed_accumulated": round(float(self._research_elapsed_accumulated), 3),
            "session_type": self.session_type,
            "is_anonymous": bool(self.is_anonymous),
            "user_id": safe_user_id,
            "user_name": safe_user_name,
            "counters": dict(self.session_counters),
            "audio_sources": dict(self.audio_source_counter),
            "scene_dwell_seconds": self._scene_dwell_snapshot(),
            "support_context": {
                "support_strip_enabled": int(getattr(self, "support_strip_enabled", 0)),
                "support_slots_total": int(getattr(self, "support_slots_total", 0)),
                "support_slots_configured": int(getattr(self, "support_slots_configured", 0)),
                "support_slots_presented": int(getattr(self, "support_slots_presented", 0)),
            },
            "system_actions": dict(self.system_action_counter),
            "pressed_elements": dict(self.pressed_element_counter),
            "has_activity": self.has_activity(),
            "last_persistence_issue": self._last_persistence_issue,
            "last_persistence_success": self._last_persistence_success,
        }

    def run_diagnostic_probe(self, user_id: str = "", user_name: str = "", mode: str = "", layout_file: str = "") -> dict:
        if mode:
            self.session_start_mode = mode
        if layout_file:
            self.current_layout_file = layout_file
        self.log_event(
            action="research_probe",
            key_raw="probe",
            key_type="diagnostic",
            text_inserted="",
            layout_file=self.current_layout_file,
            mode=self.session_start_mode,
            user_id=user_id,
            user_name=user_name,
            project_title=self.current_project_title,
            scene_id=self.current_scene_id,
            scene_title=self.current_scene_title,
            scene_index=self.current_scene_index,
        )
        json_path = None
        if self.research_ever_enabled and self.has_activity():
            json_path = self.write_session_summary(user_id=user_id, user_name=user_name, reason="diagnostic_probe")
        return {
            "session_id": self.session_id,
            "global_log_path": self.global_log_path,
            "session_summary_path": self.session_summary_path,
            "session_events_path": self.session_events_path,
            "session_summary_json_path": json_path,
            "research_ever_enabled": bool(self.research_ever_enabled),
        }

    def _stable_hash(self, value: object, prefix: str = "") -> str:
        raw = "" if value is None else str(value).strip()
        if not raw:
            return ""
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"{prefix}{digest}" if prefix else digest

    def _sanitize_csv_file(self, src: str, dst: str) -> bool:
        basename = Path(src).name
        if basename.startswith("events_"):
            pseudonym_session = None
            with open(src, "r", encoding="utf-8", newline="") as rf, open(dst, "w", encoding="utf-8", newline="") as wf:
                reader = csv.DictReader(rf)
                fieldnames = reader.fieldnames or []
                writer = csv.DictWriter(wf, fieldnames=fieldnames)
                writer.writeheader()
                for row in reader:
                    original_session = row.get("session_id", "")
                    if original_session and pseudonym_session is None:
                        pseudonym_session = self._stable_hash(original_session, "session_")
                    if pseudonym_session:
                        row["session_id"] = pseudonym_session
                    row["project_title"] = self._stable_hash(row.get("project_title", ""), "project_")
                    row["scene_id"] = self._stable_hash(row.get("scene_id", ""), "scene_")
                    row["scene_title"] = self._stable_hash(row.get("scene_title", ""), "scene_")
                    if "text_inserted" in row:
                        row["text_inserted"] = ""
                    writer.writerow(row)
            return True

        if basename == "global_log.csv":
            with open(src, "r", encoding="utf-8", newline="") as rf, open(dst, "w", encoding="utf-8", newline="") as wf:
                reader = csv.DictReader(rf)
                fieldnames = reader.fieldnames or []
                writer = csv.DictWriter(wf, fieldnames=fieldnames)
                writer.writeheader()
                for row in reader:
                    row["session_id"] = self._stable_hash(row.get("session_id", ""), "session_")
                    row["project_title"] = self._stable_hash(row.get("project_title", ""), "project_")
                    row["scene_id"] = self._stable_hash(row.get("scene_id", ""), "scene_")
                    row["scene_title"] = self._stable_hash(row.get("scene_title", ""), "scene_")
                    row["user_id"] = self._stable_hash(row.get("user_id", ""), "user_")
                    row["user_name"] = ""
                    if "text_inserted" in row:
                        row["text_inserted"] = ""
                    writer.writerow(row)
            return True

        if basename == "session_summary.csv":
            with open(src, "r", encoding="utf-8", newline="") as rf, open(dst, "w", encoding="utf-8", newline="") as wf:
                reader = csv.DictReader(rf)
                fieldnames = reader.fieldnames or []
                writer = csv.DictWriter(wf, fieldnames=fieldnames)
                writer.writeheader()
                for row in reader:
                    row["session_id"] = self._stable_hash(row.get("session_id", ""), "session_")
                    row["project_title"] = self._stable_hash(row.get("project_title", ""), "project_")
                    row["user_id"] = self._stable_hash(row.get("user_id", ""), "user_")
                    row["user_name"] = ""
                    if "final_text" in row:
                        row["final_text"] = ""
                    if "final_text_len_chars" in row:
                        row["final_text_len_chars"] = "0"
                    if "final_text_len_tokens" in row:
                        row["final_text_len_tokens"] = "0"
                    writer.writerow(row)
            return True

        return False

    def _sanitize_json_summary_file(self, src: str, dst: str) -> bool:
        basename = Path(src).name
        if not (basename.startswith("session_summary_") and basename.endswith(".json")):
            return False
        with open(src, "r", encoding="utf-8") as rf:
            payload = json.load(rf)
        payload["session_id"] = self._stable_hash(payload.get("session_id", ""), "session_")
        payload["project_title"] = self._stable_hash(payload.get("project_title", ""), "project_")
        payload["user_id"] = self._stable_hash(payload.get("user_id", ""), "user_")
        payload["user_name"] = ""
        payload["final_text"] = ""
        payload["final_text_len_chars"] = 0
        payload["final_text_len_tokens"] = 0
        current_scene = payload.get("current_scene") or {}
        if isinstance(current_scene, dict):
            current_scene["scene_id"] = self._stable_hash(current_scene.get("scene_id", ""), "scene_")
            current_scene["scene_title"] = self._stable_hash(current_scene.get("scene_title", ""), "scene_")
        dwell = payload.get("scene_dwell_seconds") or {}
        if isinstance(dwell, dict):
            payload["scene_dwell_seconds"] = {
                self._stable_hash(key, "scene_"): value for key, value in dwell.items()
            }
        with open(dst, "w", encoding="utf-8") as wf:
            json.dump(payload, wf, ensure_ascii=False, indent=2)
        return True

    def export_anonymized_dataset(self) -> str:
        export_dir = self.logs_dir / f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        export_dir.mkdir(parents=True, exist_ok=True)
        exported_files = []
        skipped_files = []

        for src in self.logs_dir.iterdir():
            fname = src.name
            if src.is_dir():
                if fname.startswith("export_"):
                    continue
                skipped_files.append(fname)
                continue
            dst = export_dir / fname
            try:
                sanitized = self._sanitize_csv_file(src, dst)
                if not sanitized:
                    sanitized = self._sanitize_json_summary_file(src, dst)
                if sanitized:
                    exported_files.append(fname)
                else:
                    skipped_files.append(fname)
            except Exception as exc:
                self._record_persistence_issue(f"export_anonymized_dataset:{fname}", exc)
                skipped_files.append(fname)

        manifest = {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "schema_version": self.schema_version,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "export_type": "anonymized_dataset",
            "notes": [
                "session_id, user_id, project_title and scene identifiers are pseudonymized with SHA-256 truncation",
                "user_name, text_inserted and final_text are removed",
                "non-log files are excluded from the anonymized export",
            ],
            "exported_files": exported_files,
            "skipped_files": skipped_files,
        }
        write_json(export_dir / "manifest.json", manifest)
        return export_dir
