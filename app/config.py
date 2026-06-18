from pathlib import Path
import csv
import sys

APP_TITLE = "Sara"
APP_SUBTITLE = "Experimental visual scene displays with hotspots and optional visual supports"
AUTHOR = "Carlos Máñez Carvajal"
APP_VERSION = "0.1.26"
APP_DISPLAY_VERSION = "0.1.26"
LICENSE_LINE = "MIT License"
CITE_LINE = (
    "Máñez Carvajal, C. (2026). "
    "Sara: Visual scene display software "
    f"(Version {APP_DISPLAY_VERSION}) [Computer software]."
)
RESEARCH_SCHEMA_VERSION = "0.2-sarab"
DEFAULT_UI_LANGUAGE = "en"

PACKAGE_DIR = Path(__file__).resolve().parent
BASE_DIR = PACKAGE_DIR.parent
IS_FROZEN = bool(getattr(sys, "frozen", False))
APP_RUNTIME_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else BASE_DIR
BUNDLED_DATA_DIR = BASE_DIR / "sarab_data"
DATA_DIR = (APP_RUNTIME_DIR / "Sara_data") if IS_FROZEN else BUNDLED_DATA_DIR
PROJECTS_DIR = DATA_DIR / "projects"
SUPPORT_STRIP_MAX_ITEMS = 3
SUPPORT_STRIP_DEFAULT_VISIBLE = False
NAVIGATION_STRIP_POSITION = "top"
SUPPORT_CARD_WIDTH = 180
SUPPORT_CARD_HEIGHT = 142
SUPPORT_CARD_VERTICAL_GAP = 52
SUPPORT_CARD_VERTICAL_GAP_DESIGN = 42
SUPPORT_CARD_VERTICAL_GAP_USER = 52
SUPPORT_CARD_DESIGN_CONTROL_HEIGHT = 30
SUPPORT_IMAGE_FIT_MODE = "cover"
CELL_IMAGE_FIT_MODE = "contain"
LOGS_DIR = DATA_DIR / "logs"
ASSETS_DIR = (BUNDLED_DATA_DIR / "assets") if IS_FROZEN else DATA_DIR / "assets"
ASSETS_ICONS_DIR = ASSETS_DIR / "icons"
ASSETS_IMAGES_DIR = ASSETS_DIR / "images"
AUDIO_DIR = DATA_DIR / "audio"
USERS_CSV = DATA_DIR / "users.csv"
SETTINGS_PATH = DATA_DIR / "settings.json"

USERS_CSV_HEADERS = [
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
]


def ensure_runtime_data_files() -> None:
    """Create writable runtime folders and a minimal users CSV when needed."""
    for path in (
        DATA_DIR,
        PROJECTS_DIR,
        LOGS_DIR,
        AUDIO_DIR,
        AUDIO_DIR / "recordings",
        DATA_DIR / "arasaac_cache",
    ):
        path.mkdir(parents=True, exist_ok=True)
    if not USERS_CSV.exists():
        default_users_csv = BUNDLED_DATA_DIR / "users.csv"
        if IS_FROZEN and default_users_csv.exists():
            USERS_CSV.write_text(default_users_csv.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            with USERS_CSV.open("w", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow(USERS_CSV_HEADERS)

DEFAULT_GRID_ROWS = 3
DEFAULT_GRID_COLS = 4
LEFT_PANEL_WEIGHT = 40
RIGHT_PANEL_WEIGHT = 60

GRID_PRESETS = [
    (2, 2),
    (2, 3),
    (3, 3),
    (3, 4),
    (4, 5),
]
GRID_PRESET_LABELS = [f"{r}x{c}" for r, c in GRID_PRESETS]

FITZGERALD_COLORS = {
    "none": "#F4F4F4",
    "noun": "#FFF0A8",
    "verb": "#CFE8A9",
    "descriptor": "#9FD7F5",
    "social": "#F8C7A8",
    "misc": "#E7D5F8",
    "question": "#FFD7E8",
}

MIN_CELL_IMAGE_SIZE = (48, 48)
MAX_SCENE_IMAGE_DISPLAY = (1100, 680)
MAX_SCENE_EDITOR_PREVIEW = (420, 220)
MAX_CELL_EDITOR_PREVIEW = (220, 120)

CELL_MAX_UPSCALE = 3.2
CELL_IMAGE_AREA_RATIO = 0.88

# Cell image rendering presets
CELL_MARGIN_RATIO_DESIGN = 0.08
CELL_MARGIN_RATIO_USER = 0.04
CELL_MAX_UPSCALE_DESIGN = 2.4
CELL_MAX_UPSCALE_USER = 3.2
CELL_TEXT_SIZE_DEFAULT = 9
CELL_TEXT_BOLD_DEFAULT = True
CELL_TEXT_UPPERCASE_DEFAULT = True
CELL_TEXT_VISIBLE_DEFAULT = True
CELL_TEXT_COLOR = "#303030"
CELL_TEXT_COLOR_NO_IMAGE = "#222222"

TYPOLOGY_TO_FITZGERALD = {
    "pronouns_people_proper": "noun",
    "noun": "noun",
    "verb": "verb",
    "descriptive_mod": "descriptor",
    "social_expressions": "social",
    "misc_function_words": "misc",
    "places": "noun",
    "important_neg_emergency": "question",
    "other": "misc",
    "none": "none",
}

DISCOURSE_FUNCTION_OPTIONS = [
    ("none", "(ninguna)"),
    ("request", "PeticiÃ³n"),
    ("negation", "NegaciÃ³n"),
    ("affirmation", "AfirmaciÃ³n / ConfirmaciÃ³n"),
    ("information", "InformaciÃ³n / DescripciÃ³n"),
    ("social", "Social / CortesÃ­a"),
    ("emotion", "EmociÃ³n / Estado interno"),
    ("emergency", "Emergencia / Urgencia"),
]

TYPOLOGY_OPTIONS = [
    ("none", "(ninguna)"),
    ("pronouns_people_proper", "Pronombres / Personas / Nombres propios"),
    ("noun", "Sustantivo"),
    ("verb", "Verbo"),
    ("descriptive_mod", "Descriptivos (adjetivos / adverbios)"),
    ("social_expressions", "Contenido social y expresiones"),
    ("misc_function_words", "MiscelÃ¡nea (artÃ­culos, preposiciones, conjunciones, etc.)"),
    ("places", "Lugares"),
    ("important_neg_emergency", "Palabras importantes / negaciones / emergencias"),
    ("other", "Otros"),
]
MIN_LEFT_PANEL_WIDTH = 280
MAX_LEFT_PANEL_WIDTH = 680
DEFAULT_CELL_TEXT = ""
DEFAULT_SCENE_TITLE = "SCENE"

SUPPORTED_IMAGE_TYPES = [
    ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
    ("All files", "*.*"),
]
SUPPORTED_AUDIO_TYPES = [
    ("Audio files", "*.wav *.mp3 *.ogg *.m4a"),
    ("All files", "*.*"),
]

def normalize_grid(rows: int | None, cols: int | None) -> tuple[int, int]:
    try:
        rows = int(rows or DEFAULT_GRID_ROWS)
        cols = int(cols or DEFAULT_GRID_COLS)
    except Exception:
        return DEFAULT_GRID_ROWS, DEFAULT_GRID_COLS
    if (rows, cols) in GRID_PRESETS:
        return rows, cols
    return DEFAULT_GRID_ROWS, DEFAULT_GRID_COLS


def total_cells(rows: int, cols: int) -> int:
    rows, cols = normalize_grid(rows, cols)
    return rows * cols


def special_cell_order(rows: int, cols: int) -> dict[int, str]:
    total = total_cells(rows, cols)
    return {
        total - 3: "speak",
        total - 2: "backspace",
        total - 1: "clear",
    }

