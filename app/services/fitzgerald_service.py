from __future__ import annotations

from app import config
from app.models import CellData


def category_for_typology(typology: str | None) -> str:
    return config.TYPOLOGY_TO_FITZGERALD.get((typology or "none").strip(), "none")


def apply_typology_to_cell(cell: CellData) -> CellData:
    cell.fitzgerald_category = category_for_typology(cell.key_typology)
    return cell


def background_for_cell(cell: CellData) -> str:
    if cell.fitzgerald_enabled:
        return config.FITZGERALD_COLORS.get(cell.fitzgerald_category, config.FITZGERALD_COLORS["none"])
    return "white"
