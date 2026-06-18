from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "manual_record_audio_test.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("manual_record_audio_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    sys.path.insert(0, str(ROOT))
    try:
        spec.loader.exec_module(module)
    finally:
        try:
            sys.path.remove(str(ROOT))
        except ValueError:
            pass
    return module


def test_manual_record_audio_script_exists_and_exposes_main():
    module = _load_script_module()

    assert SCRIPT.exists()
    assert callable(module.main)


def test_manual_record_audio_parser_defaults_do_not_require_microphone():
    module = _load_script_module()
    parser = module.build_parser()

    args = parser.parse_args([])

    assert args.seconds == 3.0
    assert args.samplerate == 44100
    assert args.channels == 1
    assert args.play is False