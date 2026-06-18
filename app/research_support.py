from __future__ import annotations

import csv
import json
from pathlib import Path
from collections import Counter
from typing import Iterable


def _as_path(path: str | Path) -> Path:
    return path if isinstance(path, Path) else Path(path)


def summary_header(counter_keys: Iterable[str]) -> list[str]:
    return [
        "timestamp",
        "session_id",
        "schema_version",
        "project_title",
        "duration_seconds",
        "mode",
        "layout_file",
        "research_enabled",
        "session_type",
        "is_anonymous",
        "user_id",
        "user_name",
        "final_text",
        "final_text_len_chars",
        "final_text_len_tokens",
        "unique_scenes_visited",
        "scene_changes",
        "support_strip_enabled",
        "support_slots_total",
        "support_slots_configured",
        "support_slots_presented",
        *list(counter_keys),
    ]


def global_log_header() -> list[str]:
    return [
        "timestamp",
        "session_id",
        "schema_version",
        "project_title",
        "event_id",
        "action",
        "key_raw",
        "key_type",
        "vocabulary_category_id",
        "vocabulary_category_label",
        "vocabulary_category_group",
        "representation_type",
        "visual_source",
        "text_inserted",
        "layout_file",
        "mode",
        "scene_id",
        "scene_title",
        "scene_index",
        "scene_focus_category_id",
        "scene_focus_category_label",
        "scene_specific_topic",
        "audio_source",
        "elapsed_seconds",
        "session_type",
        "is_anonymous",
        "support_strip_enabled",
        "support_slots_total",
        "support_slots_configured",
        "support_slots_presented",
        "hotspot_id",
        "hotspot_label",
        "click_x",
        "click_y",
        "x_norm",
        "y_norm",
        "annotated_event_id",
        "response_mark",
        "annotation_source",
        "user_id",
        "user_name",
    ]


def session_events_header() -> list[str]:
    return [
        "timestamp",
        "session_id",
        "schema_version",
        "project_title",
        "event_id",
        "action",
        "key_raw",
        "key_type",
        "vocabulary_category_id",
        "vocabulary_category_label",
        "vocabulary_category_group",
        "representation_type",
        "visual_source",
        "text_inserted",
        "layout_file",
        "mode",
        "scene_id",
        "scene_title",
        "scene_index",
        "scene_focus_category_id",
        "scene_focus_category_label",
        "scene_specific_topic",
        "audio_source",
        "elapsed_seconds",
        "session_type",
        "is_anonymous",
        "support_strip_enabled",
        "support_slots_total",
        "support_slots_configured",
        "support_slots_presented",
        "hotspot_id",
        "hotspot_label",
        "click_x",
        "click_y",
        "x_norm",
        "y_norm",
        "annotated_event_id",
        "response_mark",
        "annotation_source",
    ]


def ensure_csv_header(path: str | Path, header: list[str]) -> None:
    path = _as_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_write = True
    if path.exists():
        try:
            with path.open('r', encoding='utf-8', newline='') as f:
                first = next(csv.reader(f), None)
            needs_write = first != header
        except Exception:
            needs_write = True
    if needs_write:
        with path.open('w', encoding='utf-8', newline='') as f:
            csv.writer(f).writerow(header)


def append_csv_row(path: str | Path, row: list[object]) -> None:
    path = _as_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8', newline='') as f:
        csv.writer(f).writerow(row)


def upsert_csv_row(path: str | Path, key_index: int, key_value: str, row: list[object], header: list[str]) -> None:
    path = _as_path(path)
    ensure_csv_header(path, header)
    tmp_path = path.with_suffix(path.suffix + '.tmp')
    found = False
    with path.open('r', encoding='utf-8', newline='') as rf, tmp_path.open('w', encoding='utf-8', newline='') as wf:
        reader = csv.reader(rf)
        writer = csv.writer(wf)
        existing_header = next(reader, None)
        writer.writerow(existing_header or header)
        for existing in reader:
            if not existing:
                continue
            if len(existing) > key_index and existing[key_index] == key_value:
                writer.writerow(row)
                found = True
            else:
                writer.writerow(existing)
        if not found:
            writer.writerow(row)
    tmp_path.replace(path)


def write_json(path: str | Path, payload: dict) -> None:
    path = _as_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def counter_lines(title: str, counter: Counter, limit: int = 20) -> list[str]:
    if not counter:
        return []
    lines = ['', title]
    for key, value in counter.most_common(limit):
        lines.append(f'  - {key}: {value}')
    return lines
