from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys

from validate_windows_distribution import (
    AUTHORIZED_SARA_DATA_FILES,
    validate_distribution,
    validate_source_data,
)


def prepare_sara_data(repository: Path, distribution: Path) -> None:
    source_data = repository / "sarab_data"
    destination = distribution / "Sara_data"
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for relative in sorted(AUTHORIZED_SARA_DATA_FILES):
        source = source_data / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    distribution = repository / "dist" / "Sara"

    validate_source_data(repository)
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "Sara.spec"],
        cwd=repository,
        check=True,
    )
    if not distribution.is_dir():
        raise RuntimeError(f"PyInstaller did not create the expected distribution: {distribution}")
    prepare_sara_data(repository, distribution)
    validate_distribution(distribution, repository)
    print(f"Clean Windows distribution created: {distribution}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
