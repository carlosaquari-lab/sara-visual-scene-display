from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List

from app import config
from app.i18n import default_project_name, default_scene_title
from app.vocabulary_categories import get_vocabulary_category


@dataclass
class CellData:
    id: str
    position: int
    text: str = ""
    image_path: str = ""
    audio_path: str = ""
    tts_enabled: bool = True
    fitzgerald_enabled: bool = False
    fitzgerald_category: str = "none"
    cell_type: str = "content"
    visible: bool = True
    discourse_function: str = ""
    key_typology: str = ""
    visual_source: str = "none"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CellData":
        payload = dict(data or {})
        return cls(
            id=payload.get("id", ""),
            position=int(payload.get("position", 0)),
            text=payload.get("text", ""),
            image_path=payload.get("image_path", ""),
            audio_path=payload.get("audio_path", ""),
            tts_enabled=bool(payload.get("tts_enabled", True)),
            fitzgerald_enabled=bool(payload.get("fitzgerald_enabled", False)),
            fitzgerald_category=payload.get("fitzgerald_category", "none"),
            cell_type=payload.get("cell_type", "content"),
            visible=bool(payload.get("visible", True)),
            discourse_function=payload.get("discourse_function", ""),
            key_typology=payload.get("key_typology", ""),
            visual_source=payload.get("visual_source", "none"),
        )


def _cell_has_content(cell: CellData | None) -> bool:
    if cell is None:
        return False
    return bool(
        str(getattr(cell, "text", "") or "").strip()
        or str(getattr(cell, "image_path", "") or "").strip()
        or str(getattr(cell, "audio_path", "") or "").strip()
    )


def default_supports(max_items: int | None = None) -> List[CellData]:
    total = int(max_items or getattr(config, "SUPPORT_STRIP_MAX_ITEMS", 3) or 3)
    supports: List[CellData] = []
    for idx in range(total):
        supports.append(CellData(
            id=f"support_{idx + 1}",
            position=idx,
            text="",
            tts_enabled=True,
            cell_type="visual_support",
            fitzgerald_enabled=False,
            fitzgerald_category="none",
            visible=False,
            visual_source="none",
        ))
    return supports


def normalize_supports(scene) -> None:
    max_items = int(getattr(config, "SUPPORT_STRIP_MAX_ITEMS", 3) or 3)
    existing = {int(getattr(support, "position", idx) or idx): support for idx, support in enumerate(list(getattr(scene, "supports", []) or []))}
    defaults = default_supports(max_items)
    normalized: List[CellData] = []
    for idx in range(max_items):
        support = existing.get(idx) or defaults[idx]
        support.position = idx
        support.id = support.id or f"support_{idx + 1}"
        if not str(support.id).startswith("support_"):
            support.id = f"support_{idx + 1}"
        support.cell_type = "visual_support"
        normalized.append(support)
    scene.supports = normalized


@dataclass
class HotspotData:
    id: str
    label: str = ""
    text: str = ""
    x: float = 0.0
    y: float = 0.0
    width: float = 0.12
    height: float = 0.12
    audio_path: str = ""
    tts_enabled: bool = True
    target_scene_id: str = ""
    visible_in_design: bool = True
    vocabulary_category_id: str | None = None
    vocabulary_category_label: str | None = None
    vocabulary_category_group: str | None = None
    label_bg_color: str = "#FFFFFF"
    label_fg_color: str = "#000000"
    label_font_size: int = 16
    label_persistence_seconds: int = 5
    label_persistence_always: bool = False

    def to_dict(self) -> dict:
        payload = asdict(self)
        category_id = self.vocabulary_category_id or None
        if not category_id or str(category_id).lower() == "none":
            payload["vocabulary_category_id"] = None
            payload["vocabulary_category_label"] = None
            payload["vocabulary_category_group"] = None
        payload.pop("discourse_function", None)
        payload.pop("key_typology", None)
        payload["x"] = float(max(0.0, min(self.x, 1.0)))
        payload["y"] = float(max(0.0, min(self.y, 1.0)))
        payload["width"] = float(max(0.02, min(self.width, 1.0)))
        payload["height"] = float(max(0.02, min(self.height, 1.0)))
        return payload

    @classmethod
    def from_dict(cls, data: dict) -> "HotspotData":
        payload = dict(data or {})
        return cls(
            id=payload.get("id", ""),
            label=payload.get("label", ""),
            text=payload.get("text", ""),
            x=float(payload.get("x", 0.0) or 0.0),
            y=float(payload.get("y", 0.0) or 0.0),
            width=float(payload.get("width", 0.12) or 0.12),
            height=float(payload.get("height", 0.12) or 0.12),
            audio_path=payload.get("audio_path", ""),
            tts_enabled=bool(payload.get("tts_enabled", True)),
            target_scene_id=payload.get("target_scene_id", ""),
            visible_in_design=bool(payload.get("visible_in_design", True)),
            vocabulary_category_id=payload.get("vocabulary_category_id", None),
            vocabulary_category_label=payload.get("vocabulary_category_label", None),
            vocabulary_category_group=payload.get("vocabulary_category_group", None),
            label_bg_color=payload.get("label_bg_color", "#FFFFFF"),
            label_fg_color=payload.get("label_fg_color", "#000000"),
            label_font_size=int(payload.get("label_font_size", 16) or 16),
            label_persistence_seconds=int(payload.get("label_persistence_seconds", 5) or 5),
            label_persistence_always=bool(payload.get("label_persistence_always", False)),
        )


@dataclass
class Scene:
    id: str
    title: str = config.DEFAULT_SCENE_TITLE
    background_image: str = ""
    scene_audio: str = ""
    scene_focus_category_id: str | None = None
    scene_focus_category_label: str | None = None
    scene_specific_topic: str = ""
    cells: List[CellData] = field(default_factory=list)
    supports: List[CellData] = field(default_factory=default_supports)
    hotspots: List[HotspotData] = field(default_factory=list)

    def to_dict(self) -> dict:
        # SaraB uses explicit scene-level ``supports`` rather than the old
        # communication-grid ``cells`` field.  Empty legacy cells are omitted
        # from the saved JSON so reviewers and future readers can see that
        # supports are a distinct structural component.
        category = get_vocabulary_category(self.scene_focus_category_id)
        if category["id"] == "none":
            scene_focus_category_id = None
            scene_focus_category_label = None
        else:
            scene_focus_category_id = category["id"]
            scene_focus_category_label = self.scene_focus_category_label or category["label"]
        payload = {
            "id": self.id,
            "title": self.title,
            "background_image": self.background_image,
            "scene_audio": self.scene_audio,
            "scene_focus_category_id": scene_focus_category_id,
            "scene_focus_category_label": scene_focus_category_label,
            "scene_specific_topic": self.scene_specific_topic or "",
            "supports": [support.to_dict() for support in getattr(self, "supports", [])],
            "hotspots": [hotspot.to_dict() for hotspot in self.hotspots],
        }
        if any(_cell_has_content(cell) for cell in getattr(self, "cells", []) or []):
            payload["cells"] = [cell.to_dict() for cell in self.cells]
        return payload

    @classmethod
    def from_dict(cls, data: dict) -> "Scene":
        payload = dict(data or {})
        legacy_cells = [CellData.from_dict(item) for item in payload.get("cells", [])]
        raw_supports = payload.get("supports", None)
        if isinstance(raw_supports, list):
            supports = [CellData.from_dict(item) for item in raw_supports]
        else:
            # Backward compatibility: old Sara/SaraB projects stored the three
            # right-side visual supports in the first grid cells.  During load
            # we migrate those cells into the new explicit ``supports`` field
            # and stop treating them as a communication grid.
            supports = []
            for idx, cell in enumerate(legacy_cells[: int(getattr(config, "SUPPORT_STRIP_MAX_ITEMS", 3) or 3)]):
                migrated = CellData.from_dict(cell.to_dict())
                migrated.id = f"support_{idx + 1}"
                migrated.position = idx
                migrated.cell_type = "visual_support"
                supports.append(migrated)
        hotspots = [HotspotData.from_dict(item) for item in payload.get("hotspots", [])]
        raw_category = (
            payload.get("content_type", None)
            or payload.get("category", None)
            or payload.get("scene_focus_category_id", None)
            or payload.get("scene_focus_category_label", None)
        )
        category_aliases = {
            "object": "noun",
            "action_activity": "verb",
            "place_context": "place",
            "emotion_state": "descriptor",
            "sound_onomatopoeia": "other",
            "function_core_word": "function_word",
            "social_phrase": "social_expression",
        }
        if raw_category:
            raw_category = category_aliases.get(str(raw_category).strip(), raw_category)
        category = get_vocabulary_category(raw_category)
        scene_focus_category_id = None if category["id"] == "none" else category["id"]
        scene_focus_category_label = None if category["id"] == "none" else category["label"]
        scene = cls(
            id=payload.get("id", "scene_1"),
            title=payload.get("title", config.DEFAULT_SCENE_TITLE),
            background_image=payload.get("background_image", ""),
            scene_audio=payload.get("scene_audio", ""),
            scene_focus_category_id=scene_focus_category_id,
            scene_focus_category_label=scene_focus_category_label,
            scene_specific_topic=payload.get("scene_specific_topic", "") or "",
            cells=[],
            supports=supports,
            hotspots=hotspots,
        )
        normalize_supports(scene)
        return scene


@dataclass
class TextStyleConfig:
    size: int = config.CELL_TEXT_SIZE_DEFAULT
    bold: bool = config.CELL_TEXT_BOLD_DEFAULT
    uppercase: bool = config.CELL_TEXT_UPPERCASE_DEFAULT
    visible: bool = config.CELL_TEXT_VISIBLE_DEFAULT

    def to_dict(self) -> dict:
        return {
            "size": int(max(8, min(self.size, 16))),
            "bold": bool(self.bold),
            "uppercase": bool(self.uppercase),
            "visible": bool(self.visible),
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "TextStyleConfig":
        payload = dict(data or {})
        return cls(
            size=int(payload.get("size", config.CELL_TEXT_SIZE_DEFAULT)),
            bold=bool(payload.get("bold", config.CELL_TEXT_BOLD_DEFAULT)),
            uppercase=bool(payload.get("uppercase", config.CELL_TEXT_UPPERCASE_DEFAULT)),
            visible=bool(payload.get("visible", config.CELL_TEXT_VISIBLE_DEFAULT)),
        )


@dataclass
class ResearchSettings:
    enabled: bool = False
    current_user_id: str = ""
    current_user_name: str = ""

    def to_dict(self) -> dict:
        return {
            "enabled": bool(self.enabled),
            "current_user_id": self.current_user_id,
            "current_user_name": self.current_user_name,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "ResearchSettings":
        payload = dict(data or {})
        return cls(
            enabled=bool(payload.get("enabled", False)),
            current_user_id=payload.get("current_user_id", ""),
            current_user_name=payload.get("current_user_name", ""),
        )


@dataclass
class StoryProject:
    project_name: str = default_project_name()
    version: str = config.APP_VERSION
    initial_scene_id: str = "scene_1"
    current_scene_index: int = 0
    window_mode: str = "maximized"
    grid_rows: int = config.DEFAULT_GRID_ROWS
    grid_cols: int = config.DEFAULT_GRID_COLS
    text_style: TextStyleConfig = field(default_factory=TextStyleConfig)
    research_settings: ResearchSettings = field(default_factory=ResearchSettings)
    scenes: List[Scene] = field(default_factory=list)
    file_path: str = ""

    @property
    def total_cells(self) -> int:
        return config.total_cells(self.grid_rows, self.grid_cols)

    @property
    def cell_text_size(self) -> int:
        return self.text_style.size

    @cell_text_size.setter
    def cell_text_size(self, value: int) -> None:
        self.text_style.size = int(value)

    @property
    def cell_text_bold(self) -> bool:
        return self.text_style.bold

    @cell_text_bold.setter
    def cell_text_bold(self, value: bool) -> None:
        self.text_style.bold = bool(value)

    @property
    def cell_text_uppercase(self) -> bool:
        return self.text_style.uppercase

    @cell_text_uppercase.setter
    def cell_text_uppercase(self, value: bool) -> None:
        self.text_style.uppercase = bool(value)

    @property
    def cell_text_visible(self) -> bool:
        return self.text_style.visible

    @cell_text_visible.setter
    def cell_text_visible(self, value: bool) -> None:
        self.text_style.visible = bool(value)

    def to_dict(self) -> dict:
        return {
            "project_name": self.project_name,
            "version": self.version,
            "initial_scene_id": self.initial_scene_id,
            "current_scene_index": self.current_scene_index,
            "window_mode": self.window_mode,
            "grid": {"rows": self.grid_rows, "cols": self.grid_cols},
            "cell_text_style": self.text_style.to_dict(),
            "research_settings": self.research_settings.to_dict(),
            "scenes": [scene.to_dict() for scene in self.scenes],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StoryProject":
        payload = dict(data or {})
        grid = payload.get("grid", {}) or {}
        grid_rows, grid_cols = config.normalize_grid(grid.get("rows"), grid.get("cols"))
        scenes = [Scene.from_dict(item) for item in payload.get("scenes", [])]
        if not scenes:
            scenes = [default_scene(1, grid_rows, grid_cols)]
        project = cls(
            project_name=payload.get("project_name", default_project_name()),
            version=payload.get("version", config.APP_VERSION),
            initial_scene_id=payload.get("initial_scene_id", scenes[0].id),
            current_scene_index=int(payload.get("current_scene_index", 0)),
            window_mode=payload.get("window_mode", "maximized"),
            grid_rows=grid_rows,
            grid_cols=grid_cols,
            text_style=TextStyleConfig.from_dict(payload.get("cell_text_style", {})),
            research_settings=ResearchSettings.from_dict(payload.get("research_settings", {})),
            scenes=scenes,
        )
        for scene in project.scenes:
            normalize_scene(scene, project.grid_rows, project.grid_cols)
        project.current_scene_index = max(0, min(project.current_scene_index, len(project.scenes) - 1))
        project.text_style.size = max(8, min(project.text_style.size, 16))
        return project


def default_cells(rows: int | None = None, cols: int | None = None) -> List[CellData]:
    rows, cols = config.normalize_grid(rows, cols)
    total = config.total_cells(rows, cols)
    cells: List[CellData] = []
    for idx in range(total):
        cells.append(CellData(
            id=f"cell_{idx + 1}",
            position=idx,
            text="",
            tts_enabled=True,
            cell_type="content",
            fitzgerald_enabled=False,
            fitzgerald_category="none",
            visible=False,
        ))
    return cells


def normalize_scene(scene: Scene, rows: int | None = None, cols: int | None = None) -> None:
    rows, cols = config.normalize_grid(rows, cols)
    total = config.total_cells(rows, cols)
    existing = {cell.position: cell for cell in scene.cells}
    defaults = default_cells(rows, cols)
    normalized: List[CellData] = []
    for idx in range(total):
        cell = existing.get(idx) or defaults[idx]
        cell.position = idx
        cell.id = cell.id or f"cell_{idx + 1}"
        cell.cell_type = "content"
        normalized.append(cell)
    scene.cells = normalized
    normalized_hotspots: List[HotspotData] = []
    for idx, hotspot in enumerate(list(getattr(scene, "hotspots", []) or []), start=1):
        hotspot.id = hotspot.id or f"hotspot_{idx}"
        hotspot.x = float(max(0.0, min(hotspot.x, 1.0)))
        hotspot.y = float(max(0.0, min(hotspot.y, 1.0)))
        hotspot.width = float(max(0.02, min(hotspot.width, 1.0)))
        hotspot.height = float(max(0.02, min(hotspot.height, 1.0)))
        normalized_hotspots.append(hotspot)
    scene.hotspots = normalized_hotspots
    normalize_supports(scene)


def default_scene(number: int = 1, rows: int | None = None, cols: int | None = None) -> Scene:
    rows, cols = config.normalize_grid(rows, cols)
    return Scene(id=f"scene_{number}", title=default_scene_title(number), cells=default_cells(rows, cols), supports=default_supports(), hotspots=[])
