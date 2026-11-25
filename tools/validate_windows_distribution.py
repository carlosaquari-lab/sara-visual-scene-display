from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys


PROJECT_FILES = (
    "projects/Breakfast at Home.json",
    "projects/Breakfast at Home_assets/images/IMG_20260531_104515_3f6f0ab40c15.webp",
    "projects/Breakfast at Home_assets/images/IMG_20260621_114503_ac1d35e66e6c.webp",
    "projects/Breakfast at Home_assets/images/IMG_20260621_114907_2e316cb26463.webp",
    "projects/Breakfast at Home_assets/images/IMG_20260621_115248_f12ee286d8e3.webp",
    "projects/Breakfast at Home_assets/images/support_coffee_beans_v2_824145bad1f7.webp",
    "projects/Breakfast at Home_assets/images/support_coffee_cup_v2_34ed4e89a6e5.webp",
    "projects/Breakfast at Home_assets/images/support_coffee_maker_v2_9d7fc59f1f61.webp",
    "projects/PREPARING PASTA AT HOME.json",
    "projects/PREPARING PASTA AT HOME_assets/images/IMG_20260531_173413_8471cc767d18.webp",
    "projects/PREPARING PASTA AT HOME_assets/images/IMG_20260621_120414_5481aed6b8d6.webp",
    "projects/PREPARING PASTA AT HOME_assets/images/IMG_20260621_123548_71e76d8611b9.webp",
    "projects/PREPARING PASTA AT HOME_assets/images/colador_8823b52bddfb.webp",
    "projects/PREPARING PASTA AT HOME_assets/images/garlic3_a47bcfb65c68.webp",
    "projects/PREPARING PASTA AT HOME_assets/images/pepper5_aaba1da5f270.webp",
    "projects/PREPARING PASTA AT HOME_assets/images/tomato3_f974aa1be597.webp",
)

RUNTIME_SCAFFOLD_FILES = (
    "logs/README.txt",
    "arasaac_cache/README.txt",
    "audio/recordings/README.txt",
    "users.csv",
)

AUTHORIZED_SARA_DATA_FILES = frozenset((*PROJECT_FILES, *RUNTIME_SCAFFOLD_FILES))

STATIC_ICON_FILES = frozenset(
    {
        "assets/icons/altavoz.png",
        "assets/icons/altavoz_scene.png",
        "assets/icons/backspace.png",
        "assets/icons/gear_fine_36.png",
        "assets/icons/hotspot_add.png",
        "assets/icons/hotspot_delete.png",
        "assets/icons/hotspot_edit.png",
        "assets/icons/hotspot_select.png",
        "assets/icons/mode_edit_bw.png",
        "assets/icons/mode_stop_bw.png",
        "assets/icons/mode_user_play.png",
        "assets/icons/mode_user_play_bw.png",
        "assets/icons/mode_user_play_round.png",
        "assets/icons/modify_scene.png",
        "assets/icons/papelera.png",
        "assets/icons/scene_next.png",
        "assets/icons/scene_previous.png",
        "assets/icons/settings.png",
        "assets/icons/settings_bw.png",
        "assets/icons/wrench.png",
        "assets/icons/wrench_clear.png",
    }
)

USERS_HEADER = (
    "id",
    "name",
    "notes",
    "group",
    "layout_file",
    "date_created",
    "last_session_date",
    "last_session_end",
    "total_sessions",
    "total_key_presses",
    "total_words_inserted",
    "total_characters_inserted",
    "total_time_seconds",
)

AUTHORIZED_DEMO_USER = (
    "example",
    "Example user",
    "Demonstration account",
    "example",
    "",
    "",
    "",
    "",
    "0",
    "0",
    "0",
    "0",
    "0",
)

PROJECT_JSON_FILES = (
    "projects/Breakfast at Home.json",
    "projects/PREPARING PASTA AT HOME.json",
)

PATH_FIELDS = frozenset({"background_image", "image_path", "audio_path", "scene_audio"})


class DistributionValidationError(RuntimeError):
    pass


def _relative_files(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}


def _relative_directories(root: Path) -> set[str]:
    return {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_dir()}


def _required_directories(files: set[str] | frozenset[str]) -> set[str]:
    directories: set[str] = set()
    for relative in files:
        parent = Path(relative).parent
        while parent != Path("."):
            directories.add(parent.as_posix())
            parent = parent.parent
    return directories


def _reject_symlinks(root: Path) -> None:
    if root.is_symlink():
        raise DistributionValidationError(f"Symbolic links are not allowed: {root}")
    for path in root.rglob("*"):
        if path.is_symlink():
            raise DistributionValidationError(f"Symbolic links are not allowed: {path}")


def _assert_exact_tree(root: Path, expected_files: frozenset[str], label: str) -> None:
    if not root.is_dir():
        raise DistributionValidationError(f"Missing {label} directory: {root}")
    _reject_symlinks(root)
    actual_files = _relative_files(root)
    missing = sorted(expected_files - actual_files)
    unexpected = sorted(actual_files - expected_files)
    if missing or unexpected:
        raise DistributionValidationError(
            f"Invalid {label} file set; missing={missing or 'none'}, unexpected={unexpected or 'none'}"
        )
    expected_directories = _required_directories(expected_files)
    actual_directories = _relative_directories(root)
    missing_directories = sorted(expected_directories - actual_directories)
    unexpected_directories = sorted(actual_directories - expected_directories)
    if missing_directories or unexpected_directories:
        raise DistributionValidationError(
            "Invalid "
            f"{label} directory set; missing={missing_directories or 'none'}, "
            f"unexpected={unexpected_directories or 'none'}"
        )


def _validate_users_csv(path: Path) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        rows = list(csv.reader(csv_file))
    expected = [list(USERS_HEADER), list(AUTHORIZED_DEMO_USER)]
    if rows != expected:
        raise DistributionValidationError(
            "users.csv must contain exactly the authorized public demonstration account 'example'"
        )


def _load_json(path: Path) -> object:
    try:
        with path.open("r", encoding="utf-8") as json_file:
            return json.load(json_file)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DistributionValidationError(f"Invalid project JSON: {path}: {exc}") from exc


def _iter_project_paths(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in PATH_FIELDS and isinstance(child, str) and child.strip():
                yield child.strip()
            yield from _iter_project_paths(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_project_paths(child)


def _validate_project_references(projects_root: Path) -> None:
    for relative in PROJECT_JSON_FILES:
        json_path = projects_root.parent / relative
        payload = _load_json(json_path)
        for raw_reference in _iter_project_paths(payload):
            normalized = raw_reference.replace("\\", "/")
            reference = Path(normalized)
            if reference.is_absolute() or ".." in reference.parts:
                raise DistributionValidationError(
                    f"Unsafe asset reference in {json_path.name}: {raw_reference}"
                )
            resolved = projects_root / reference
            if not resolved.is_file():
                raise DistributionValidationError(
                    f"Referenced asset is missing for {json_path.name}: {raw_reference}"
                )
            relative_asset = f"projects/{reference.as_posix()}"
            if relative_asset not in AUTHORIZED_SARA_DATA_FILES:
                raise DistributionValidationError(
                    f"Referenced asset is not authorized for distribution: {raw_reference}"
                )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_hashes(output_root: Path, source_root: Path, relative_files: frozenset[str], label: str) -> None:
    for relative in sorted(relative_files):
        output = output_root / relative
        source = source_root / relative
        if _sha256(output) != _sha256(source):
            raise DistributionValidationError(f"{label} differs from its approved source: {relative}")


def validate_source_data(source_root: str | Path) -> None:
    repository = Path(source_root).resolve()
    source_data = repository / "sarab_data"
    expected_source_files = frozenset(
        {"README.txt", *AUTHORIZED_SARA_DATA_FILES, *STATIC_ICON_FILES}
    )
    _assert_exact_tree(source_data, expected_source_files, "source sarab_data")
    _validate_users_csv(source_data / "users.csv")
    _validate_project_references(source_data / "projects")


def validate_distribution(distribution_dir: str | Path, source_root: str | Path | None = None) -> None:
    distribution = Path(distribution_dir).resolve()
    repository = Path(source_root).resolve() if source_root is not None else Path(__file__).resolve().parents[1]
    if not distribution.is_dir():
        raise DistributionValidationError(f"Distribution directory does not exist: {distribution}")
    _reject_symlinks(distribution)

    root_entries = {path.name for path in distribution.iterdir()}
    expected_root_entries = {"Sara.exe", "_internal", "Sara_data"}
    if root_entries != expected_root_entries:
        raise DistributionValidationError(
            f"Distribution root must contain only {sorted(expected_root_entries)}; found {sorted(root_entries)}"
        )
    if not (distribution / "Sara.exe").is_file():
        raise DistributionValidationError("Sara.exe is missing")
    if not (distribution / "_internal").is_dir():
        raise DistributionValidationError("_internal is missing")

    sara_data = distribution / "Sara_data"
    _assert_exact_tree(sara_data, AUTHORIZED_SARA_DATA_FILES, "Sara_data")
    _validate_users_csv(sara_data / "users.csv")
    _validate_project_references(sara_data / "projects")

    internal_data = distribution / "_internal" / "sarab_data"
    _assert_exact_tree(internal_data, STATIC_ICON_FILES, "internal static data")

    source_data = repository / "sarab_data"
    _validate_hashes(sara_data, source_data, AUTHORIZED_SARA_DATA_FILES, "Distributed Sara_data file")
    _validate_hashes(internal_data, source_data, STATIC_ICON_FILES, "Internal static resource")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a clean Sara Windows distribution")
    parser.add_argument("distribution", help="Path to the Sara distribution directory")
    parser.add_argument(
        "--source-root",
        default=str(Path(__file__).resolve().parents[1]),
        help="Repository root containing the approved sarab_data source",
    )
    args = parser.parse_args(argv)
    try:
        validate_source_data(args.source_root)
        validate_distribution(args.distribution, args.source_root)
    except DistributionValidationError as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"Validation passed: {Path(args.distribution).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
