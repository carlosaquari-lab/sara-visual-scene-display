Sara 0.1.26 — support visibility fixed LIGHT package

Base:
- Manual validation completed after restoring SceneImageViewService.render().
- Safety policy validated: in user mode, non-hotspot clicks do not trigger scene audio.
- Last local validation reported by the user: 124 passed, 1 warning.

This LIGHT package intentionally excludes:
- .venv/
- __pycache__/
- .pytest_cache/
- old CHANGES_*.txt files
- sara_startup_error.txt
- CLEANUP_REPORT.txt
- runtime logs
- generated example projects and their images
- ARASAAC cache images
- users.csv

Kept:
- app/
- tests/
- tools/
- sarab_data/assets/
- README/LICENSE/requirements
- launch scripts and icons

Suggested commands on Windows:
    py -3.12 -m pip install -r requirements.txt
    py -3.12 -m pip install pytest
    py -3.12 -m pytest -q
    py -3.12 run_sara.py

Note:
The empty folders sarab_data/projects, sarab_data/logs and sarab_data/arasaac_cache are kept so the app can recreate runtime files.

