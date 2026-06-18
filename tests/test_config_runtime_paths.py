import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config as config_module


def _reload_config():
    return importlib.reload(config_module)


def test_development_mode_keeps_existing_sarab_data_paths(monkeypatch):
    with monkeypatch.context() as m:
        m.delattr(sys, "frozen", raising=False)
        cfg = _reload_config()

        assert cfg.DATA_DIR == cfg.BASE_DIR / "sarab_data"
        assert cfg.PROJECTS_DIR == cfg.DATA_DIR / "projects"
        assert cfg.USERS_CSV == cfg.DATA_DIR / "users.csv"
        assert cfg.SETTINGS_PATH == cfg.DATA_DIR / "settings.json"
        assert cfg.LOGS_DIR == cfg.DATA_DIR / "logs"
        assert cfg.ASSETS_DIR == cfg.DATA_DIR / "assets"

    _reload_config()


def test_frozen_mode_uses_sara_data_next_to_exe_for_mutable_paths(tmp_path, monkeypatch):
    exe_dir = tmp_path / "Sara"
    exe_dir.mkdir()
    exe_path = exe_dir / "Sara.exe"
    exe_path.write_text("", encoding="utf-8")

    with monkeypatch.context() as m:
        m.setattr(sys, "frozen", True, raising=False)
        m.setattr(sys, "executable", str(exe_path))
        cfg = _reload_config()

        assert cfg.DATA_DIR == exe_dir / "Sara_data"
        assert cfg.USERS_CSV == exe_dir / "Sara_data" / "users.csv"
        assert cfg.SETTINGS_PATH == exe_dir / "Sara_data" / "settings.json"
        assert cfg.LOGS_DIR == exe_dir / "Sara_data" / "logs"
        assert cfg.AUDIO_DIR == exe_dir / "Sara_data" / "audio"

    _reload_config()


def test_frozen_mode_keeps_static_assets_in_bundled_sarab_data(tmp_path, monkeypatch):
    exe_dir = tmp_path / "Sara"
    exe_dir.mkdir()
    exe_path = exe_dir / "Sara.exe"
    exe_path.write_text("", encoding="utf-8")

    with monkeypatch.context() as m:
        m.setattr(sys, "frozen", True, raising=False)
        m.setattr(sys, "executable", str(exe_path))
        cfg = _reload_config()

        assert cfg.ASSETS_DIR == cfg.BUNDLED_DATA_DIR / "assets"
        assert cfg.ASSETS_ICONS_DIR == cfg.BUNDLED_DATA_DIR / "assets" / "icons"
        assert cfg.DATA_DIR != cfg.BUNDLED_DATA_DIR

    _reload_config()


def test_ensure_runtime_data_files_creates_sara_data_and_users_csv(tmp_path, monkeypatch):
    exe_dir = tmp_path / "Sara"
    exe_dir.mkdir()
    exe_path = exe_dir / "Sara.exe"
    exe_path.write_text("", encoding="utf-8")

    with monkeypatch.context() as m:
        m.setattr(sys, "frozen", True, raising=False)
        m.setattr(sys, "executable", str(exe_path))
        cfg = _reload_config()
        fake_bundle = tmp_path / "_internal" / "sarab_data"
        m.setattr(cfg, "BUNDLED_DATA_DIR", fake_bundle)

        cfg.ensure_runtime_data_files()

        assert cfg.DATA_DIR.exists()
        assert cfg.LOGS_DIR.exists()
        assert (cfg.AUDIO_DIR / "recordings").exists()
        assert (cfg.DATA_DIR / "arasaac_cache").exists()
        assert cfg.USERS_CSV.exists()
        header = cfg.USERS_CSV.read_text(encoding="utf-8").splitlines()[0]
        assert header == ",".join(cfg.USERS_CSV_HEADERS)

    _reload_config()
