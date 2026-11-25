from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil

import pytest

from tools.validate_windows_distribution import (
    AUTHORIZED_DEMO_USER,
    AUTHORIZED_SARA_DATA_FILES,
    DistributionValidationError,
    STATIC_ICON_FILES,
    USERS_HEADER,
    validate_distribution,
    validate_source_data,
)


def _write_users(path: Path, row=AUTHORIZED_DEMO_USER) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(USERS_HEADER)
        writer.writerow(row)


def _project_payload(reference: str) -> dict:
    return {
        "version": "0.1.26",
        "project_name": "Public example",
        "scenes": [{"id": "scene_1", "background_image": reference, "hotspots": [], "supports": []}],
    }


def _make_source(root: Path) -> Path:
    source_data = root / "sarab_data"
    for relative in AUTHORIZED_SARA_DATA_FILES:
        path = source_data / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"approved:{relative}".encode("utf-8"))
    for relative in STATIC_ICON_FILES:
        path = source_data / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"icon:{relative}".encode("utf-8"))
    (source_data / "README.txt").write_text("Runtime data", encoding="utf-8")
    _write_users(source_data / "users.csv")
    (source_data / "projects" / "Breakfast at Home.json").write_text(
        json.dumps(
            _project_payload(
                "Breakfast at Home_assets\\images\\IMG_20260531_104515_3f6f0ab40c15.webp"
            )
        ),
        encoding="utf-8",
    )
    (source_data / "projects" / "PREPARING PASTA AT HOME.json").write_text(
        json.dumps(
            _project_payload(
                "PREPARING PASTA AT HOME_assets\\images\\IMG_20260531_173413_8471cc767d18.webp"
            )
        ),
        encoding="utf-8",
    )
    return root


def _make_distribution(tmp_path: Path) -> tuple[Path, Path]:
    source = _make_source(tmp_path / "source")
    distribution = tmp_path / "dist" / "Sara"
    (distribution / "_internal" / "sarab_data").mkdir(parents=True)
    (distribution / "Sara.exe").write_bytes(b"test executable")
    for relative in AUTHORIZED_SARA_DATA_FILES:
        target = distribution / "Sara_data" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / "sarab_data" / relative, target)
    for relative in STATIC_ICON_FILES:
        target = distribution / "_internal" / "sarab_data" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / "sarab_data" / relative, target)
    return source, distribution


def test_valid_distribution_passes(tmp_path):
    source, distribution = _make_distribution(tmp_path)

    validate_source_data(source)
    validate_distribution(distribution, source)


def test_additional_project_is_rejected(tmp_path):
    source, distribution = _make_distribution(tmp_path)
    (distribution / "Sara_data" / "projects" / "Private.json").write_text("{}", encoding="utf-8")

    with pytest.raises(DistributionValidationError, match="unexpected.*Private.json"):
        validate_distribution(distribution, source)


def test_additional_asset_is_rejected(tmp_path):
    source, distribution = _make_distribution(tmp_path)
    extra = distribution / "Sara_data" / "projects" / "Breakfast at Home_assets" / "images" / "extra.webp"
    extra.write_bytes(b"private")

    with pytest.raises(DistributionValidationError, match="unexpected.*extra.webp"):
        validate_distribution(distribution, source)


def test_missing_referenced_asset_is_rejected(tmp_path):
    source, distribution = _make_distribution(tmp_path)
    project = distribution / "Sara_data" / "projects" / "Breakfast at Home.json"
    project.write_text(json.dumps(_project_payload("Breakfast at Home_assets\\images\\missing.webp")), encoding="utf-8")

    with pytest.raises(DistributionValidationError, match="Referenced asset is missing"):
        validate_distribution(distribution, source)


@pytest.mark.parametrize(
    ("relative", "content"),
    [
        ("logs/session.csv", b"private log"),
        ("arasaac_cache/12345.png", b"cached pictogram"),
        ("audio/recordings/voice.wav", b"private recording"),
        ("settings.json", b"{}"),
        ("projects/build.tmp", b"temporary"),
    ],
    ids=["log-csv", "real-cache", "wav-recording", "settings", "temporary-file"],
)
def test_runtime_content_is_rejected(tmp_path, relative, content):
    source, distribution = _make_distribution(tmp_path)
    unexpected = distribution / "Sara_data" / relative
    unexpected.parent.mkdir(parents=True, exist_ok=True)
    unexpected.write_bytes(content)

    with pytest.raises(DistributionValidationError, match="unexpected"):
        validate_distribution(distribution, source)


def test_unauthorized_user_is_rejected(tmp_path):
    source, distribution = _make_distribution(tmp_path)
    unauthorized = list(AUTHORIZED_DEMO_USER)
    unauthorized[0] = "real-user"
    unauthorized[1] = "Real Person"
    _write_users(distribution / "Sara_data" / "users.csv", unauthorized)

    with pytest.raises(DistributionValidationError, match="authorized public demonstration account"):
        validate_distribution(distribution, source)


def test_source_data_with_additional_project_fails_closed(tmp_path):
    source = _make_source(tmp_path / "source")
    (source / "sarab_data" / "projects" / "Private.json").write_text("{}", encoding="utf-8")

    with pytest.raises(DistributionValidationError, match="unexpected.*Private.json"):
        validate_source_data(source)
