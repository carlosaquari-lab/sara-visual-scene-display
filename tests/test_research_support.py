from __future__ import annotations

import csv

import pytest

from app.research import ResearchLogger
from app.research_support import ensure_csv_header, global_log_header, summary_header


def test_ensure_csv_header_creates_missing_file(tmp_path):
    path = tmp_path / "new.csv"

    ensure_csv_header(path, ["one", "two"])

    with path.open("r", encoding="utf-8", newline="") as csv_file:
        assert next(csv.reader(csv_file)) == ["one", "two"]


def test_ensure_csv_header_initializes_empty_file(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_bytes(b"")

    ensure_csv_header(path, ["one", "two"])

    with path.open("r", encoding="utf-8", newline="") as csv_file:
        assert next(csv.reader(csv_file)) == ["one", "two"]


def test_ensure_csv_header_leaves_matching_file_unchanged(tmp_path):
    path = tmp_path / "matching.csv"
    original = b"one,two\r\nvalue,other\r\n"
    path.write_bytes(original)

    ensure_csv_header(path, ["one", "two"])

    assert path.read_bytes() == original


def test_ensure_csv_header_rejects_incompatible_header_without_changing_any_bytes(tmp_path):
    path = tmp_path / "existing.csv"
    original = b"old,columns\r\nvaluable,data\r\n"
    path.write_bytes(original)

    with pytest.raises(ValueError, match="Incompatible CSV header.*preserved"):
        ensure_csv_header(path, ["new", "header"])

    assert path.read_bytes() == original


def test_research_logger_preserves_incompatible_global_log_and_starts_with_current_header(tmp_path):
    path = tmp_path / "global_log.csv"
    original = b"old,columns\r\nvaluable,global-data\r\n"
    path.write_bytes(original)

    research = ResearchLogger(tmp_path, schema_version="0.1-sara", app_name="Sara", app_version="test")

    preserved = list(tmp_path.glob("global_log.incompatible_*.csv"))
    assert len(preserved) == 1
    assert preserved[0].read_bytes() == original
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        assert next(csv.reader(csv_file)) == global_log_header()
    research.set_research_enabled(True)
    research.log_event(action="key_press", key_raw="DELETE", key_type="special")
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        assert len(list(csv.DictReader(csv_file))) >= 1


def test_research_logger_preserves_incompatible_summary_and_starts_with_current_header(tmp_path):
    path = tmp_path / "session_summary.csv"
    original = b"old,columns\r\nvaluable,summary-data\r\n"
    path.write_bytes(original)

    research = ResearchLogger(tmp_path, schema_version="0.1-sara", app_name="Sara", app_version="test")

    preserved = list(tmp_path.glob("session_summary.incompatible_*.csv"))
    assert len(preserved) == 1
    assert preserved[0].read_bytes() == original
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        assert next(csv.reader(csv_file)) == summary_header(research._empty_counters().keys())
    research.set_research_enabled(True)
    research.log_event(action="key_press", key_raw="DELETE", key_type="special")
    research.write_session_summary(reason="test")
    with path.open("r", encoding="utf-8", newline="") as csv_file:
        assert len(list(csv.DictReader(csv_file))) == 1
