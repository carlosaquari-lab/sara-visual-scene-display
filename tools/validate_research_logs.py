"""Validate Sara research logs for common state-machine inconsistencies.

Usage:
    python tools/validate_research_logs.py sara_data/logs
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def validate(logs_dir: Path) -> list[str]:
    issues: list[str] = []
    if not logs_dir.exists():
        return [f"logs_dir_not_found: {logs_dir}"]

    for events_path in sorted(logs_dir.glob("events_*.csv")):
        sid_from_name = events_path.stem.replace("events_", "", 1)
        rows = read_csv(events_path)
        if not rows:
            issues.append(f"empty_events_file: {events_path.name}")
            continue
        session_ids = {str(row.get("session_id", "")) for row in rows if row.get("session_id", "")}
        if session_ids != {sid_from_name}:
            issues.append(f"filename_session_mismatch: {events_path.name} rows={sorted(session_ids)}")
        actions = {row.get("action", "") for row in rows}
        if "toggle_research_on" not in actions:
            issues.append(f"missing_toggle_research_on: {events_path.name}")
        if "toggle_research_off" not in actions:
            issues.append(f"missing_toggle_research_off: {events_path.name}")

    for json_path in sorted(logs_dir.glob("session_summary_*.json")):
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append(f"invalid_json: {json_path.name}: {exc}")
            continue
        if payload.get("reason") == "disable_research" and payload.get("research_enabled") is True:
            issues.append(f"disable_reason_but_enabled_true: {json_path.name}")

    return issues


def main() -> int:
    logs_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sara_data/logs")
    issues = validate(logs_dir)
    if not issues:
        print("OK: no research log inconsistencies detected.")
        return 0
    print("Research log issues detected:")
    for issue in issues:
        print(f"- {issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
