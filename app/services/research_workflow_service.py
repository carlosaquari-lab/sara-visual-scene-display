from __future__ import annotations

from app.i18n import tr
from app.services.dialog_service import DialogService
from app.ui.ui_research_diagnostics import show_research_diagnostics_dialog
import csv
from collections import Counter, defaultdict

from app.ui.ui_session_stats import show_session_stats_dialog
from app.ui_dialogs import UserSelectionDialog


class ResearchWorkflowService:
    """Coordinate research enablement, identity handling and research dialogs."""

    def __init__(self, research, users_manager, dialog_service: DialogService | None = None):
        self.research = research
        self.users_manager = users_manager
        self.dialogs = dialog_service or DialogService()

    def ensure_participant_policy(self, parent, select_user_callback) -> bool:
        if self.users_manager.current_user_id:
            try:
                self.research.set_participant_context(session_type="participant", is_anonymous=False)
            except Exception:
                pass
            return True

        choice = self.dialogs.confirm_yes_no_cancel(
            tr("research_user_prompt_title"),
            tr("research_user_prompt"),
            parent=parent,
        )
        if choice is None:
            return False
        if choice is True:
            select_user_callback()
            if self.users_manager.current_user_id:
                try:
                    self.research.set_participant_context(session_type="participant", is_anonymous=False)
                except Exception:
                    pass
                return True
            return False
        try:
            self.research.set_participant_context(session_type="test", is_anonymous=True)
        except Exception:
            pass
        return True

    def toggle_research(self, parent, current_enabled: bool, current_user_id: str, current_user_name: str, select_user_callback) -> bool | None:
        """Switch research ON/OFF using one explicit and auditable state transition."""
        enabling = not bool(current_enabled)
        if enabling:
            if not self.ensure_participant_policy(parent, select_user_callback):
                return None
            try:
                self.research.start_new_session(reason="enable_research", write_previous=False)
                self.research.set_enabled(True)
                self.research.log_research_toggle(
                    "toggle_research_on",
                    user_id=current_user_id or self.users_manager.current_user_id or "",
                    user_name=current_user_name or self.users_manager.get_current_user_name() or "",
                    reason="enable_research",
                )
            except Exception as exc:
                try:
                    self.research.set_enabled(False)
                    self.research._record_persistence_issue("toggle_research_on", exc)
                except Exception:
                    pass
                self.dialogs.error(
                    tr("research"),
                    f"No se pudo activar el módulo de investigación.\nError: {exc}",
                    parent=parent,
                )
                return None
            return True

        try:
            # Log OFF while the session is still enabled so the event is written
            # into events_<session_id>.csv and global_log.csv. Then disable and
            # flush; the summary will therefore contain research_enabled=False.
            self.research.log_research_toggle(
                "toggle_research_off",
                user_id=current_user_id or "",
                user_name=current_user_name or "",
                reason="disable_research",
            )
            self.research.set_enabled(False)
            self.research.flush_session_if_needed(
                user_id=current_user_id or "",
                user_name=current_user_name or "",
                reason="disable_research",
            )
        except Exception as exc:
            try:
                self.research._record_persistence_issue("toggle_research_off", exc)
            except Exception:
                pass
            self.dialogs.error(
                tr("research"),
                f"No se pudo desactivar correctamente el módulo de investigación.\nError: {exc}",
                parent=parent,
            )
            return None
        return False

    def open_user_selection(self, parent, on_select) -> None:
        dlg = UserSelectionDialog(parent, self.users_manager, on_select)
        try:
            parent.wait_window(dlg)
        except Exception:
            pass

    def force_session_summary(self) -> dict:
        return self.research.force_write_summary(
            user_id=self.users_manager.current_user_id or "",
            user_name=self.users_manager.get_current_user_name() or "",
        )

    def identity_for_display(self) -> tuple[str, str]:
        ctx = self.research.get_participant_context()
        if bool(ctx.get("is_anonymous", True)) or str(ctx.get("session_type", "test")) == "test":
            return "", ""
        return self.users_manager.current_user_id or "", self.users_manager.get_current_user_name() or ""

    def _read_current_session_event_rows(self) -> list[dict]:
        path = getattr(self.research, "session_events_path", None)
        if not path:
            return []
        try:
            with open(path, "r", encoding="utf-8", newline="") as fh:
                return [dict(row) for row in csv.DictReader(fh)]
        except Exception:
            return []

    @staticmethod
    def _top_counter(counter: Counter, limit: int = 8) -> list[tuple[str, int]]:
        return [(str(key), int(value)) for key, value in counter.most_common(limit) if str(key or "").strip()]

    @staticmethod
    def _stable_key(value) -> str:
        return str(value or "").strip().lower()

    def _session_stats_event_summaries(self, scene_order: list[dict] | None = None) -> dict:
        rows = self._read_current_session_event_rows()
        scenes: dict[str, dict] = {}
        ordered_keys: list[str] = []
        text_outputs = Counter()
        hotspot_activity = Counter()
        support_activity = Counter()

        for index, scene_info in enumerate(list(scene_order or [])):
            scene_id = str(scene_info.get("id") or "").strip()
            scene_title = str(scene_info.get("title") or f"Scene {index + 1}").strip() or f"Scene {index + 1}"
            scene_key = scene_id or scene_title or f"scene_{index + 1}"
            ordered_keys.append(scene_key)
            scenes[scene_key] = {
                "title": scene_title,
                "events": 0,
                "hotspots": 0,
                "supports": 0,
                "texts": Counter(),
                "turn": 0,
                "correct": 0,
                "incorrect": 0,
            }

        for row in rows:
            scene_key = str(row.get("scene_id") or row.get("scene_title") or "unknown")
            scene_title = str(row.get("scene_title") or scene_key or "-")
            scene = scenes.setdefault(scene_key, {
                "title": scene_title,
                "events": 0,
                "hotspots": 0,
                "supports": 0,
                "texts": Counter(),
                "turn": 0,
                "correct": 0,
                "incorrect": 0,
            })
            if scene_key not in ordered_keys:
                ordered_keys.append(scene_key)
            scene["events"] += 1

            action = self._stable_key(row.get("action"))
            key_type = self._stable_key(row.get("key_type"))
            text = str(row.get("text_inserted") or row.get("key_raw") or "").strip()
            hotspot_label = str(row.get("hotspot_label") or "").strip()

            if key_type in {"scene_hotspot", "scene_hotspot_audio"} or hotspot_label:
                scene["hotspots"] += 1
                label = hotspot_label or text
                if label:
                    hotspot_activity[label] += 1
            if key_type in {"visual_support", "visual_support_audio"}:
                scene["supports"] += 1
                if text:
                    support_activity[text] += 1
            if action == "key_press" and text:
                text_outputs[text] += 1
                scene["texts"][text] += 1

            if action == "response_mark_annotation":
                mark = str(row.get("response_mark") or "unmarked").strip().lower()
                if mark in {"turn", "correct", "incorrect"}:
                    scene[mark] += 1

        scene_rows = []
        for scene_key in ordered_keys:
            scene = scenes[scene_key]
            scene_rows.append({
                "title": scene["title"],
                "events": scene["events"],
                "hotspots": scene["hotspots"],
                "supports": scene["supports"],
                "texts": self._top_counter(scene["texts"], 5),
                "turn": scene["turn"],
                "correct": scene["correct"],
                "incorrect": scene["incorrect"],
            })

        return {
            "scene_rows": scene_rows,
            "text_outputs": self._top_counter(text_outputs, 10),
            "hotspot_activity": self._top_counter(hotspot_activity, 10),
            "support_activity": self._top_counter(support_activity, 10),
        }

    def build_session_stats_payload(self, project_name: str, current_scene_index: int, total_scenes: int, rows: int, cols: int, mode: str, scene_order: list[dict] | None = None) -> dict:
        session_context = self.research.get_participant_context()
        display_user_name = self.users_manager.get_current_user_name() or ""
        session_counters = dict(self.research.session_counters)
        session_counters["session_elapsed_s"] = self.research.get_session_elapsed_seconds()
        response_mark_counts = {
            "unmarked": int(session_counters.get("unmarked_count", 0) or 0),
            "turn": int(session_counters.get("turn_count", 0) or 0),
            "correct": int(session_counters.get("correct_count", 0) or 0),
            "incorrect": int(session_counters.get("incorrect_count", 0) or 0),
        }
        return {
            "project_name": project_name,
            "current_scene_index": current_scene_index,
            "total_scenes": total_scenes,
            "rows": rows,
            "cols": cols,
            "mode": mode,
            "research_enabled": self.research.research_enabled,
            "research_ever_enabled": getattr(self.research, "research_ever_enabled", False),
            "session_closed": getattr(self.research, "_session_closed", False),
            "session_id": getattr(self.research, "session_id", ""),
            "session_event_count": getattr(self.research, "_session_event_count", 0),
            "hotspot_activation_count": int(getattr(self.research, "keytype_counter", {}).get("scene_hotspot", 0) or 0),
            "response_mark_counts": response_mark_counts,
            "scene_title": getattr(self.research, "current_scene_title", ""),
            "scene_focus_category_id": getattr(self.research, "current_scene_focus_category_id", ""),
            "scene_focus_category_label": getattr(self.research, "current_scene_focus_category_label", ""),
            "scene_specific_topic": getattr(self.research, "current_scene_specific_topic", ""),
            "user_name": display_user_name or "—",
            "session_type": session_context.get("session_type", "test"),
            "is_anonymous": session_context.get("is_anonymous", True),
            "session_counters": session_counters,
            "word_counter": self.research.word_counter,
            "key_counter": self.research.key_counter,
            "system_action_counter": self.research.system_action_counter,
            "pressed_element_counter": self.research.pressed_element_counter,
            "representation_counter": self.research.representation_counter,
            "typology_counter": getattr(self.research, "typology_counter", {}),
            "function_counter": getattr(self.research, "function_counter", {}),
            "audio_source_counter": self.research.audio_source_counter,
            "scene_dwell_counter": self.research._scene_dwell_counter,
            "support_context": {
                "support_strip_enabled": int(getattr(self.research, "support_strip_enabled", 0)),
                "support_slots_total": int(getattr(self.research, "support_slots_total", 0)),
                "support_slots_configured": int(getattr(self.research, "support_slots_configured", 0)),
                "support_slots_presented": int(getattr(self.research, "support_slots_presented", 0)),
            },
            "event_summaries": self._session_stats_event_summaries(scene_order),
        }

    def build_research_diagnostics_snapshot(self) -> dict:
        user_id, user_name = self.identity_for_display()
        return self.research.get_status_snapshot(
            user_id=user_id,
            user_name=user_name,
        )

    def show_session_stats(self, parent, project_name: str, current_scene_index: int, total_scenes: int, rows: int, cols: int, mode: str, scene_order: list[dict] | None = None) -> None:
        session_context = self.research.get_participant_context()
        session_counters = dict(self.research.session_counters)
        session_counters["session_elapsed_s"] = self.research.get_session_elapsed_seconds()
        show_session_stats_dialog(
            parent,
            project_name=project_name,
            current_scene_index=current_scene_index,
            total_scenes=total_scenes,
            rows=rows,
            cols=cols,
            mode=mode,
            research_enabled=self.research.research_enabled,
            research_ever_enabled=getattr(self.research, "research_ever_enabled", False),
            session_closed=getattr(self.research, "_session_closed", False),
            session_event_count=getattr(self.research, "_session_event_count", 0),
            user_name=self.users_manager.get_current_user_name() or "—",
            session_type=session_context.get("session_type", "test"),
            is_anonymous=session_context.get("is_anonymous", True),
            session_counters=session_counters,
            word_counter=self.research.word_counter,
            key_counter=self.research.key_counter,
            system_action_counter=self.research.system_action_counter,
            pressed_element_counter=self.research.pressed_element_counter,
            representation_counter=self.research.representation_counter,
            typology_counter=getattr(self.research, "typology_counter", {}),
            function_counter=getattr(self.research, "function_counter", {}),
            audio_source_counter=self.research.audio_source_counter,
            scene_dwell_counter=self.research._scene_dwell_counter,
            support_context={
                "support_strip_enabled": int(getattr(self.research, "support_strip_enabled", 0)),
                "support_slots_total": int(getattr(self.research, "support_slots_total", 0)),
                "support_slots_configured": int(getattr(self.research, "support_slots_configured", 0)),
                "support_slots_presented": int(getattr(self.research, "support_slots_presented", 0)),
            },
            event_summaries=self._session_stats_event_summaries(scene_order),
        )

    def show_research_diagnostics(self, parent) -> None:
        user_id, user_name = self.identity_for_display()
        snapshot = self.research.get_status_snapshot(
            user_id=user_id,
            user_name=user_name,
        )
        show_research_diagnostics_dialog(parent, snapshot)
