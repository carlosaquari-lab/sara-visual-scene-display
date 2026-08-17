# Sara 0.1.26

Sara is a desktop application for creating and using interactive Visual Scene Display (VSD) activities. It allows users to prepare scene-based communication materials with manually defined hotspots, configurable visual supports, optional audio or text-to-speech output, and session logging for research or professional review.

The software is designed to support the preparation of visual communication activities in educational, clinical, and research contexts. Sara stores projects locally using JSON files and associated asset folders, making activities editable, reusable, and easy to inspect.

This public release includes two demonstration projects:

- Breakfast at Home
- PREPARING PASTA AT HOME

The example materials are provided for demonstration purposes only and do not represent real users, patients, or clinical sessions.

## Installation

Sara 0.1.26 has been developed and tested on Microsoft Windows with Python 3.12. Microsoft Windows is the currently supported and validated environment. Linux and macOS have not been formally validated. Tkinter and Tcl/Tk must be available in the Python installation; they are normally included with the official Windows Python distribution.

Install the runtime dependencies with:

```bash
python -m pip install -r requirements.txt
```

For testing or building the PyInstaller distribution, also install:

```bash
python -m pip install -r requirements-dev.txt
```

## Run

```bash
python run_sara.py
```

`run_sara.py` is the official entrypoint.

On Windows, `run_sara.pyw` and `INICIAR_SARA.bat` provide optional launchers.

## Tests

Sara 0.1.26 has a verified automated pytest suite of 211 passing tests. The suite covers:

- project persistence;
- hotspot geometry and coordinate handling, including conversion of normalized hotspot coordinates using the current rendered image dimensions;
- hit testing;
- movement;
- resizing;
- boundary handling;
- selected Tkinter runtime-safety checks;
- audio-recording workflows;
- research/session logging.

```bash
python -m compileall app tests
python -m pytest -q
```

Some Tkinter tests require a working graphical Tcl/Tk installation and may not
run in a headless environment. No formal percentage-based code-coverage metric
has been calculated. Manual validation remains necessary for interface layout
and device-dependent audio recording and playback.

The current verified suite result is 211 passed, 0 failed, 0 skipped, 1 warning.

## Local data and example projects

The repository includes two non-clinical demonstration projects under
`sarab_data/projects/`, together with the assets required to load them:

- `Breakfast at Home`
- `PREPARING PASTA AT HOME`

During source execution, local users, settings, research logs, downloaded
ARASAAC resources, and temporary recordings are stored under `sarab_data/`.
These generated or local files are excluded from version control. In a packaged
PyInstaller build, mutable data are stored in the user-facing `Sara_data/`
folder next to the executable, while bundled interface assets remain internal.

## License and third-party assets

Sara source code is released under the MIT License.

Copyright (c) 2026 Carlos Máñez-Carvajal.

Documentation, article-related materials, example projects, images, audio files, and third-party resources may have different licensing conditions. See `ASSETS_LICENSE.md` for details.

The included example projects contain demonstration materials for documenting
and reproducing Sara workflows. They do not represent real users, patients, or
therapy sessions, and no personal or clinical data are included.

Sara may allow users to incorporate external visual supports, including ARASAAC pictograms, into their own projects. ARASAAC pictograms are licensed separately under CC BY-NC-SA and are not covered by Sara’s MIT license.


## Hotspot communication categories

Hotspots use a research field named `Research: Communication category`. The category set is a generic Sara classification for communication/vocabulary metadata. It is not a diagnostic instrument and is not based on or intended to reproduce a protected clinical vocabulary assessment. The hotspot editor displays the categories in three compact columns, while the definitions are centralized in `app/vocabulary_categories.py`.

Each hotspot can store one selected communication category:

```json
{
  "vocabulary_category_id": "person",
  "vocabulary_category_label": "Person / proper name",
  "vocabulary_category_group": "sara_communication"
}
```

If no category is selected, the three category metadata fields are stored as `null` or omitted by the serialization layer when appropriate.

## Research logs

When research is enabled, Sara writes logs to `sarab_data/logs/` during source execution and to `Sara_data/logs/` in a packaged build. Event files and session summaries are created only when there is real research activity. New hotspot events use `vocabulary_category_id`, `vocabulary_category_label`, and `vocabulary_category_group` as the active hotspot communication-category fields.

Session summaries may include category-oriented metrics such as `category_counts` and `top_vocabulary_categories`.

## Status

Sara 0.1.26 is a functional pre-1.0 release that remains under continued development and refinement.
