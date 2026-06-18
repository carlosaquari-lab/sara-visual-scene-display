import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config
from app import ui_main
from app.ui_main import SaraApp


def test_open_project_initial_dir_prefers_exe_example_projects_when_packaged(tmp_path, monkeypatch):
    exe_dir = tmp_path / "Sara"
    examples_dir = exe_dir / "Example_projects"
    examples_dir.mkdir(parents=True)
    exe_path = exe_dir / "Sara.exe"
    exe_path.write_text("", encoding="utf-8")
    app = object.__new__(SaraApp)

    monkeypatch.setattr(ui_main.sys, "frozen", True, raising=False)
    monkeypatch.setattr(ui_main.sys, "executable", str(exe_path))

    assert app._open_project_initial_dir() == str(examples_dir)


def test_open_project_initial_dir_falls_back_to_config_projects_dir(tmp_path, monkeypatch):
    exe_dir = tmp_path / "Sara"
    exe_dir.mkdir(parents=True)
    exe_path = exe_dir / "Sara.exe"
    exe_path.write_text("", encoding="utf-8")
    app = object.__new__(SaraApp)

    monkeypatch.setattr(ui_main.sys, "frozen", True, raising=False)
    monkeypatch.setattr(ui_main.sys, "executable", str(exe_path))

    assert app._open_project_initial_dir() == str(config.PROJECTS_DIR)
