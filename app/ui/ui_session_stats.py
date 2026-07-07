from __future__ import annotations

import tkinter as tk
from collections import Counter
from tkinter import ttk

from app import config
from app.i18n import tr


def _bool_text(value: bool) -> str:
    return tr("bool_yes") if bool(value) else tr("bool_no")


def _localized_label(kind: str, key: str) -> str:
    if kind == "representation":
        mapping = {
            "text_only": tr("stats_repr_text_only"),
            "image_only": tr("stats_repr_image_only"),
            "pictogram_only": tr("stats_repr_pictogram_only"),
            "text_image": tr("stats_repr_text_image"),
            "text_pictogram": tr("stats_repr_text_pictogram"),
            "mixed": tr("stats_repr_mixed"),
            "scene_hotspot": tr("stats_pressed_other_input"),
            "other": tr("stats_repr_other"),
        }
    elif kind == "pressed_element":
        mapping = {
            "communicative_cell": tr("stats_hotspots_activated_label"),
            "system_action": tr("stats_pressed_system_action"),
            "quick_phrase": tr("stats_pressed_quick_phrase"),
            "scene_audio": tr("stats_pressed_scene_audio"),
            "physical_keyboard": tr("stats_pressed_physical_keyboard"),
            "other_input": tr("stats_pressed_other_input"),
        }
    else:
        mapping = {}
    return mapping.get(key, key)


def _counter_items(counter: Counter | dict | None, top_n: int = 10):
    if isinstance(counter, Counter):
        return counter.most_common(top_n)
    return list((counter or {}).items())[:top_n]


def _section_lines(title: str, counter: Counter | dict | None, top_n: int = 10, kind: str | None = None) -> list[str]:
    items = [(str(k), v) for k, v in _counter_items(counter, top_n) if str(k or "").strip()]
    lines = [title]
    if not items:
        lines.append(f"- {tr('stats_no_data')}")
        return lines
    for key, value in items:
        label = _localized_label(kind, key) if kind else key
        lines.append(f"- {label}: {value}")
    return lines


def _pair_lines(title: str, items: list[tuple[str, int]] | None) -> list[str]:
    lines = [title.upper()]
    clean_items = [(str(label), int(value)) for label, value in list(items or []) if str(label or "").strip()]
    if not clean_items:
        lines.append(f"- {tr('stats_no_data')}")
        return lines
    for label, value in clean_items:
        lines.append(f"- {label}: {value}")
    return lines


def _scene_breakdown_lines(scene_rows: list[dict] | None) -> list[str]:
    lines = [tr("stats_scene_breakdown_section").upper()]
    rows = list(scene_rows or [])
    if not rows:
        lines.append(f"- {tr('stats_no_data')}")
        return lines
    for scene in rows:
        title = str(scene.get("title") or "-")
        category = str(scene.get("scene_focus_category_label") or "").strip() or tr("no_category")
        topic = str(scene.get("scene_specific_topic") or "").strip() or tr("no_specific_topic")
        texts = ", ".join(label for label, _count in list(scene.get("texts") or [])[:4]) or tr("stats_no_data")
        lines.extend([
            "",
            title.upper(),
            f"- {tr('scene_category', value=category)}",
            f"- {tr('scene_specific_topic', value=topic)}",
            f"- {tr('stats_scene_events').capitalize()}: {scene.get('events', 0)}",
            f"- {tr('stats_scene_hotspots').capitalize()}: {scene.get('hotspots', 0)}",
            f"- {tr('stats_scene_supports').capitalize()}: {scene.get('supports', 0)}",
            f"- {tr('stats_scene_texts').capitalize()}: {texts}",
            f"- {tr('stats_scene_turns').capitalize()}: {scene.get('turn', 0)}",
            f"- {tr('stats_corrects')}: {scene.get('correct', 0)}",
            f"- {tr('stats_incorrects')}: {scene.get('incorrect', 0)}",
        ])
    return lines


def _int_value(mapping: dict, key: str) -> int:
    try:
        return int(mapping.get(key, 0) or 0)
    except Exception:
        return 0


def _response_mark_counts(session_counters: dict, response_mark_counts: dict | None = None) -> dict:
    counts = dict(response_mark_counts or {})
    return {
        "turn": _int_value(counts, "turn") or _int_value(session_counters, "turn_count"),
        "correct": _int_value(counts, "correct") or _int_value(session_counters, "correct_count"),
        "incorrect": _int_value(counts, "incorrect") or _int_value(session_counters, "incorrect_count"),
        "unmarked": _int_value(counts, "unmarked") or _int_value(session_counters, "unmarked_count"),
    }


def _has_session_data(session_event_count: int, session_counters: dict, hotspot_activation_count: int, response_mark_counts: dict | None) -> bool:
    if int(session_event_count or 0) > 0:
        return True
    if int(hotspot_activation_count or 0) > 0:
        return True
    counts = _response_mark_counts(session_counters, response_mark_counts)
    if any(counts.get(key, 0) for key in ("turn", "correct", "incorrect")):
        return True
    activity_keys = ("total_key_presses", "total_support_activations", "total_audio_file_plays", "total_tts_plays")
    return any(_int_value(session_counters, key) for key in activity_keys)


def _format_stats(
    project_name,
    current_scene_index,
    total_scenes,
    rows,
    cols,
    mode,
    research_enabled,
    user_name,
    session_type,
    is_anonymous,
    session_counters,
    word_counter=None,
    key_counter=None,
    system_action_counter=None,
    pressed_element_counter=None,
    representation_counter=None,
    typology_counter=None,
    function_counter=None,
    audio_source_counter=None,
    scene_dwell_counter=None,
    support_context=None,
    research_ever_enabled=False,
    session_closed=False,
    session_event_count=0,
    session_id="",
    scene_title="",
    scene_focus_category_id="",
    scene_focus_category_label="",
    scene_specific_topic="",
    hotspot_activation_count=0,
    last_hotspot_label="",
    last_response_mark="unmarked",
    response_mark_counts=None,
    event_summaries=None,
) -> str:
    if not _has_session_data(session_event_count, session_counters, hotspot_activation_count, response_mark_counts):
        return tr("stats_no_session_data")

    if research_enabled:
        session_state = tr("stats_research_state_open")
    elif session_closed and research_ever_enabled:
        session_state = tr("stats_research_state_closed")
    elif research_ever_enabled:
        session_state = tr("stats_research_state_paused")
    else:
        session_state = tr("stats_research_state_inactive")

    counts = _response_mark_counts(session_counters, response_mark_counts)
    mark_key = str(last_response_mark or "unmarked").strip().lower()
    if mark_key not in {"unmarked", "turn", "correct", "incorrect"}:
        mark_key = "unmarked"

    lines = [
        tr("stats_session_data_section").upper(),
        tr("stats_user", value=user_name or "-"),
        tr("stats_project", project=project_name or "-"),
        tr("stats_session_id", value=session_id or "-"),
        tr("stats_scene", current=current_scene_index + 1, total=total_scenes),
        tr("stats_scene_title", value=scene_title or "-"),
        tr("scene_category", value=scene_focus_category_label or tr("no_category")),
        tr("scene_specific_topic", value=scene_specific_topic or tr("no_specific_topic")),
        tr("stats_mode", mode=mode),
        tr("stats_research", value=_bool_text(research_enabled)),
        tr("stats_research_state", value=session_state),
        "",
        tr("stats_automatic_activity_section").upper(),
        tr("stats_events_recorded", value=int(session_event_count or 0)),
        tr("stats_hotspots_activated", value=int(hotspot_activation_count or 0)),
        f"- {tr('stats_total_time')}: {session_counters.get('session_elapsed_s', 0)}",
        f"- {tr('stats_support_activations')}: {session_counters.get('total_support_activations', 0)}",
        f"- {tr('stats_tts')}: {session_counters.get('total_tts_plays', 0)}",
        f"- {tr('stats_audio')}: {session_counters.get('total_audio_file_plays', 0)}",
        f"- {tr('stats_supports')}: {(support_context or {}).get('support_slots_presented', 0)} / {(support_context or {}).get('support_slots_configured', 0)}",
        "",
        tr("stats_clinician_annotation_section").upper(),
        tr("stats_last_hotspot", value=last_hotspot_label or "-"),
        tr("stats_last_mark", value=tr(f"response_mark_{mark_key}")),
        f"- {tr('stats_turns')}: {counts['turn']}",
        f"- {tr('stats_corrects')}: {counts['correct']}",
        f"- {tr('stats_incorrects')}: {counts['incorrect']}",
        "",
    ]
    summaries = event_summaries or {}
    lines.extend(_scene_breakdown_lines(summaries.get("scene_rows")))
    lines.append("")
    lines.extend(_pair_lines(tr("stats_text_outputs_section"), summaries.get("text_outputs")))
    lines.append("")
    lines.extend(_pair_lines(tr("stats_hotspot_activity_section"), summaries.get("hotspot_activity")))
    lines.append("")
    lines.extend(_pair_lines(tr("stats_support_activity_section"), summaries.get("support_activity")))
    return "\n".join(lines).strip()


def _build_clipboard_summary(stats_text: str, app_name: str | None = None, app_version: str | None = None) -> str:
    name = app_name or getattr(config, "APP_TITLE", "Sara")
    version = app_version or getattr(config, "APP_DISPLAY_VERSION", getattr(config, "APP_VERSION", ""))
    heading = f"{name} {version}".strip()
    body = (stats_text or "").strip() or tr("stats_no_session_data")
    return f"{heading}\n{tr('stats_clipboard_title')}\n\n{body}".strip()


def show_session_stats_dialog(master, **kwargs):
    win = tk.Toplevel(master)
    win.title(tr("stats_title"))
    win.transient(master)
    win.grab_set()
    win.geometry("900x780")
    win.minsize(820, 640)

    frame = ttk.Frame(win, padding=12)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=tr("stats_header"), font=("Arial", 12, "bold")).pack(anchor="w")
    ttk.Label(frame, text=tr("stats_intro"), foreground="#555555").pack(anchor="w", pady=(0, 8))

    text_frame = ttk.Frame(frame)
    text_frame.pack(fill="both", expand=True)

    scrollbar = ttk.Scrollbar(text_frame, orient="vertical")
    text = tk.Text(text_frame, wrap="word", height=24, font=("Consolas", 10), yscrollcommand=scrollbar.set)
    scrollbar.config(command=text.yview)
    text.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    stats_text = _format_stats(**kwargs)
    text.insert("1.0", stats_text)
    text.configure(state="disabled")

    button_row = ttk.Frame(frame)
    button_row.pack(fill="x", pady=(10, 0))
    copy_status_var = tk.StringVar(value="")

    def copy_summary() -> None:
        summary = _build_clipboard_summary(stats_text)
        try:
            win.clipboard_clear()
            win.clipboard_append(summary)
            win.update_idletasks()
            copy_status_var.set(tr("stats_summary_copied"))
        except Exception:
            copy_status_var.set("")

    ttk.Button(button_row, text=tr("copy_summary"), command=copy_summary).pack(side="left")
    ttk.Label(button_row, textvariable=copy_status_var, foreground="#555555").pack(side="left", padx=(10, 0))
    ttk.Button(button_row, text=tr("close"), command=win.destroy).pack(side="right")
    return win
