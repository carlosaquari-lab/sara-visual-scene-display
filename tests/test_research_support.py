from __future__ import annotations

import csv

import pytest

from app.research_support import ensure_csv_header


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
