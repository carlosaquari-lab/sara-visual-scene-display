import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_run_sara_imports_and_exposes_main_entrypoint():
    module = importlib.import_module("run_sara")

    assert callable(module.main)


def test_run_sarab_remains_compatibility_wrapper_for_official_run_sara():
    source = (ROOT / "run_sarab.py").read_text(encoding="utf-8")
    pyw_source = (ROOT / "run_sarab.pyw").read_text(encoding="utf-8")

    assert "from run_sara import main" in source
    assert "from run_sara import main" in pyw_source
