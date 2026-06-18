from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app.i18n import tr


def _bool_text(value: bool) -> str:
    return tr("bool_yes") if bool(value) else tr("bool_no")


def _format_snapshot(snapshot: dict) -> str:
    research_enabled = bool(snapshot.get("research_enabled", False))
    session_type = str(snapshot.get("session_type", "test"))
    mode_label = snapshot.get("mode", "") or "—"
    session_type_label = tr("session_participant") if session_type == "participant" else tr("session_test")
    anonymous_label = _bool_text(snapshot.get("is_anonymous", True))
    ok = tr("label_ok")
    missing = tr("label_missing")
    if research_enabled:
        session_state = tr("stats_research_state_open")
    elif snapshot.get("session_closed") and snapshot.get("research_ever_enabled"):
        session_state = tr("stats_research_state_closed")
    elif snapshot.get("research_ever_enabled"):
        session_state = tr("stats_research_state_paused")
    else:
        session_state = tr("stats_research_state_inactive")
    lines = [
        tr("diag_technical_state"),
        "",
        tr("diag_research_enabled", value=_bool_text(research_enabled)),
        tr("diag_research_state", value=session_state),
        tr("diag_event_count", value=snapshot.get("session_event_count", 0)),
        tr("diag_last_closed", value=snapshot.get("last_research_closed_at", "") or "—"),
        tr("diag_session_id", value=snapshot.get("session_id", "") or "—"),
        tr("diag_schema", value=snapshot.get("schema_version", "") or "—"),
        tr("diag_mode", value=mode_label),
        tr("diag_project_file", value=snapshot.get("layout_file", "") or "—"),
        tr("diag_session_type", value=session_type_label),
        tr("diag_anonymous", value=anonymous_label),
        tr("diag_user_id", value=snapshot.get("user_id", "") or "—"),
        tr("diag_user", value=snapshot.get("user_name", "") or "—"),
        "",
        tr("diag_files_header"),
        tr("diag_logs_folder", value=snapshot.get("logs_dir", "") or "—"),
        tr("diag_global_log", value=ok if snapshot.get("global_log_exists") else missing),
        tr("diag_summary", value=ok if snapshot.get("session_summary_exists") else missing),
        tr("diag_events", value=ok if snapshot.get("session_events_exists") else tr("label_not_created_yet")),
        "",
        tr("diag_activity", value=_bool_text(snapshot.get("has_activity", False))),
        "",
        tr("diag_footer"),
    ]
    return "\n".join(lines)


def show_research_diagnostics_dialog(master, snapshot: dict):
    win = tk.Toplevel(master)
    win.title(tr("diagnostics_title"))
    win.transient(master)
    win.grab_set()
    win.geometry("760x560")
    win.minsize(700, 500)

    frame = ttk.Frame(win, padding=12)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=tr("diagnostics_header"), font=("Arial", 12, "bold")).pack(anchor="w")
    ttk.Label(frame, text=tr("diagnostics_intro"), foreground="#555555").pack(anchor="w", pady=(0, 8))

    text = tk.Text(frame, wrap="word", height=24, font=("Consolas", 10))
    text.pack(fill="both", expand=True)
    text.insert("1.0", _format_snapshot(snapshot))
    text.configure(state="disabled")

    button_row = ttk.Frame(frame)
    button_row.pack(fill="x", pady=(10, 0))
    ttk.Button(button_row, text=tr("close"), command=win.destroy).pack(side="right")
    return win
