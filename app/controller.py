from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app import config
from app.i18n import default_project_name, localize_project_name, localize_scene_title, tr
from app.models import CellData, HotspotData, Scene, StoryProject, TextStyleConfig, default_supports, normalize_supports
from app.services.scene_service import (
    apply_grid_to_project,
    create_scene,
    duplicate_scene,
    move_scene,
    remove_scene,
)
from app.services.text_service import append_token, clear_text, normalize_style, remove_last_token, visible_text
from app.storage import infer_project_name_from_path, load_project, new_project, previous_scene_index, save_project


@dataclass
class CellActivationResult:
    action: str = "ignored"  # ignored | edit | insert
    new_text: str = ""
    inserted_text: str = ""
    audio_path: str = ""
    speak_text: str = ""
    tts_enabled: bool = False
    discourse_function: str = ""
    key_typology: str = ""
    fitzgerald_category: str = ""
    visual_source: str = "none"
    representation_type: str = "other"


@dataclass
class HotspotActivationResult:
    action: str = "ignored"
    new_text: str = ""
    inserted_text: str = ""
    audio_path: str = ""
    speak_text: str = ""
    tts_enabled: bool = False
    target_scene_id: str = ""
    vocabulary_category_id: str = ""
    vocabulary_category_label: str = ""
    vocabulary_category_group: str = ""
    representation_type: str = "text_only"


class AppController:
    def __init__(self):
        self.current_mode = "design"
        self.project: StoryProject = new_project(default_project_name(), config.DEFAULT_GRID_ROWS, config.DEFAULT_GRID_COLS)
        self.current_scene_index = 0

    @property
    def current_scene(self) -> Scene:
        return self.project.scenes[self.current_scene_index]

    def set_mode(self, mode: str) -> None:
        self.current_mode = mode if mode in {"design", "user"} else "design"

    def create_new_project(self, name: str | None = None) -> StoryProject:
        self.project = new_project(name or default_project_name(), config.DEFAULT_GRID_ROWS, config.DEFAULT_GRID_COLS)
        self.current_scene_index = 0
        return self.project

    def open_project(self, path: str) -> StoryProject:
        self.project = load_project(path)
        self.current_scene_index = max(0, min(self.project.current_scene_index, len(self.project.scenes) - 1))
        return self.project

    def save_project(self, path: Optional[str] = None) -> str:
        if path:
            self.project.project_name = infer_project_name_from_path(path)
            self.project.file_path = path
        if not self.project.file_path:
            raise ValueError("Project path is required")
        self.project.current_scene_index = self.current_scene_index
        save_project(self.project, self.project.file_path)
        return self.project.file_path

    def project_status(self, current_user: str, research_enabled: bool) -> dict:
        if self.current_mode == "design":
            return {
                "project": tr("project_prefix", name=self.project.project_name),
                "scene_title": self.current_scene.title,
                "scene": tr("scene_status", current=self.current_scene_index + 1, total=len(self.project.scenes)),
                "mode": tr("mode_status_design"),
                "grid": tr("grid_status", rows=self.project.grid_rows, cols=self.project.grid_cols),
                "user": tr("user_status", user=current_user or "—"),
                "research": tr("research_status", state=tr("state_on") if research_enabled else tr("state_off")),
            }
        return {
            "project": tr("project_prefix", name=self.project.project_name),
            "scene_title": self.current_scene.title,
            "scene": tr("scene_status", current=self.current_scene_index + 1, total=len(self.project.scenes)),
            "mode": tr("mode_status_user"),
            "grid": tr("grid_status", rows=self.project.grid_rows, cols=self.project.grid_cols),
            "user": tr("user_status", user=current_user or "—"),
            "research": tr("research_status", state=tr("state_on") if research_enabled else tr("state_off")),
        }

    def scene_selector_values(self) -> list[str]:
        values = []
        for idx, scene in enumerate(self.project.scenes, start=1):
            title = localize_scene_title(scene.title, idx)
            values.append(f"{idx}. {title}")
        return values

    def select_scene(self, index: int) -> Scene:
        return self.go_to_scene(index)

    def add_scene(self, title: str | None = None) -> Scene:
        scene = create_scene(self.project, title=title)
        self.current_scene_index = len(self.project.scenes) - 1
        return scene

    def duplicate_scene(self) -> Scene:
        self.current_scene_index = duplicate_scene(self.project, self.current_scene_index)
        return self.current_scene

    def delete_scene(self) -> Scene:
        self.current_scene_index = remove_scene(self.project, self.current_scene_index)
        return self.current_scene

    def go_to_scene(self, index: int) -> Scene:
        self.current_scene_index = max(0, min(int(index), len(self.project.scenes) - 1))
        return self.current_scene

    def next_scene(self) -> Scene:
        return self.go_to_scene(min(self.current_scene_index + 1, len(self.project.scenes) - 1))

    def previous_scene(self) -> Scene:
        return self.go_to_scene(previous_scene_index(self.current_scene_index))

    def update_scene(self, scene: Scene) -> Scene:
        current = self.current_scene
        current.title = scene.title
        current.background_image = scene.background_image
        current.scene_audio = scene.scene_audio
        current.scene_focus_category_id = scene.scene_focus_category_id
        current.scene_focus_category_label = scene.scene_focus_category_label
        current.scene_specific_topic = scene.scene_specific_topic
        return current

    def rename_scene(self, index: int, title: str) -> Scene:
        index = max(0, min(int(index), len(self.project.scenes) - 1))
        clean = (title or "").strip() or tr("scene_badge", index=index + 1)
        self.project.scenes[index].title = clean
        return self.project.scenes[index]

    def move_scene(self, from_index: int, to_index: int) -> Scene:
        self.current_scene_index = move_scene(self.project, from_index, to_index)
        return self.current_scene

    def apply_grid(self, rows: int, cols: int) -> None:
        apply_grid_to_project(self.project, rows, cols)
        self.current_scene_index = min(self.current_scene_index, len(self.project.scenes) - 1)

    def apply_grid_label(self, value: str) -> bool:
        value = (value or "").strip().lower()
        try:
            rows, cols = value.split("x")
            rows, cols = int(rows), int(cols)
        except Exception:
            return False
        if (rows, cols) == (self.project.grid_rows, self.project.grid_cols):
            return False
        self.apply_grid(rows, cols)
        return True

    def scene_audio_payload(self) -> dict:
        scene = self.current_scene
        return {"audio_path": scene.scene_audio, "speak_text": scene.title, "tts_enabled": True}

    def update_cell(self, index: int, cell: CellData) -> CellData:
        self.current_scene.cells[index] = cell
        return cell

    def get_cell(self, index: int) -> CellData:
        return self.current_scene.cells[index]

    def update_support(self, index: int, support: CellData) -> CellData:
        index = int(index)
        if not hasattr(self.current_scene, "supports") or self.current_scene.supports is None:
            self.current_scene.supports = default_supports()
        normalize_supports(self.current_scene)
        self.current_scene.supports[index] = support
        normalize_supports(self.current_scene)
        return support

    def get_support(self, index: int) -> CellData:
        index = int(index)
        if not hasattr(self.current_scene, "supports") or self.current_scene.supports is None:
            self.current_scene.supports = default_supports()
        normalize_supports(self.current_scene)
        return self.current_scene.supports[index]

    def build_cell_token(self, index: int) -> str:
        cell = self.get_cell(index)
        return visible_text(cell.text, uppercase=self.project.text_style.uppercase)

    def build_support_token(self, index: int) -> str:
        support = self.get_support(index)
        return visible_text(support.text, uppercase=self.project.text_style.uppercase)

    def _visual_source_for_cell(self, cell: CellData) -> str:
        path = str(getattr(cell, 'image_path', '') or '').strip()
        if not path:
            return 'none'
        filename = path.replace('\\', '/').split('/')[-1].lower()
        if filename.startswith('arasaac_'):
            return 'arasaac'
        return 'local_image'

    def _representation_type_for_cell(self, cell: CellData) -> str:
        has_text = bool(str(getattr(cell, 'text', '') or '').strip())
        visual_source = self._visual_source_for_cell(cell)
        if has_text and visual_source == 'none':
            return 'text_only'
        if not has_text and visual_source == 'local_image':
            return 'image_only'
        if not has_text and visual_source == 'arasaac':
            return 'pictogram_only'
        if has_text and visual_source == 'local_image':
            return 'text_image'
        if has_text and visual_source == 'arasaac':
            return 'text_pictogram'
        if has_text or visual_source != 'none':
            return 'mixed'
        return 'other'

    def activate_cell(self, index: int, current_text: str) -> CellActivationResult:
        if index < 0 or index >= self.project.total_cells:
            return CellActivationResult(action="ignored")
        cell = self.get_cell(index)
        if self.current_mode == "design":
            return CellActivationResult(action="edit")
        inserted = self.build_cell_token(index)
        new_text = append_token(current_text, inserted) if inserted else current_text
        return CellActivationResult(
            action="insert",
            new_text=new_text,
            inserted_text=inserted,
            audio_path=cell.audio_path,
            speak_text=inserted,
            tts_enabled=cell.tts_enabled,
            discourse_function=cell.discourse_function,
            key_typology=cell.key_typology,
            fitzgerald_category=cell.fitzgerald_category,
            visual_source=self._visual_source_for_cell(cell),
            representation_type=self._representation_type_for_cell(cell),
        )

    def activate_support(self, index: int, current_text: str) -> CellActivationResult:
        max_items = int(getattr(config, "SUPPORT_STRIP_MAX_ITEMS", 3) or 3)
        if index < 0 or index >= max_items or index >= len(self.current_scene.supports):
            return CellActivationResult(action="ignored")
        support = self.get_support(index)
        if self.current_mode == "design":
            return CellActivationResult(action="edit")
        inserted = self.build_support_token(index)
        new_text = append_token(current_text, inserted) if inserted else current_text
        return CellActivationResult(
            action="insert",
            new_text=new_text,
            inserted_text=inserted,
            audio_path=support.audio_path,
            speak_text=inserted or str(getattr(support, "text", "") or ""),
            tts_enabled=support.tts_enabled,
            discourse_function=support.discourse_function,
            key_typology=support.key_typology,
            fitzgerald_category=support.fitzgerald_category,
            visual_source=self._visual_source_for_cell(support),
            representation_type=self._representation_type_for_cell(support),
        )

    def activate_hotspot(self, hotspot: HotspotData, current_text: str) -> HotspotActivationResult:
        if self.current_mode == "design" or hotspot is None:
            return HotspotActivationResult(action="ignored")
        inserted = visible_text(getattr(hotspot, "text", ""), uppercase=self.project.text_style.uppercase)
        new_text = append_token(current_text, inserted) if inserted else current_text
        fallback_label = str(getattr(hotspot, "label", "") or "").strip()
        speak_text = inserted or fallback_label
        representation_type = "text_only" if inserted else "scene_hotspot"
        return HotspotActivationResult(
            action="insert",
            new_text=new_text,
            inserted_text=inserted,
            audio_path=getattr(hotspot, "audio_path", "") or "",
            speak_text=speak_text,
            tts_enabled=bool(getattr(hotspot, "tts_enabled", True)),
            target_scene_id=str(getattr(hotspot, "target_scene_id", "") or ""),
            vocabulary_category_id=str(getattr(hotspot, "vocabulary_category_id", "") or ""),
            vocabulary_category_label=str(getattr(hotspot, "vocabulary_category_label", "") or ""),
            vocabulary_category_group=str(getattr(hotspot, "vocabulary_category_group", "") or ""),
            representation_type=representation_type,
        )

    def scene_index_from_id(self, scene_id: str | None) -> int | None:
        target = str(scene_id or "").strip()
        if not target:
            return None
        for idx, scene in enumerate(self.project.scenes):
            if str(getattr(scene, "id", "")) == target:
                return idx
        return None

    def append_to_output(self, current_text: str, token: str) -> str:
        return append_token(current_text, token)

    def backspace_output(self, current_text: str) -> str:
        return remove_last_token(current_text)

    def clear_output(self) -> str:
        return clear_text()

    def update_text_style(self, size: int, bold: bool, uppercase: bool, visible: bool) -> TextStyleConfig:
        style = normalize_style({"size": size, "bold": bold, "uppercase": uppercase, "visible": visible})
        self.project.text_style = TextStyleConfig(**style)
        return self.project.text_style

    def cell_style_dict(self) -> dict:
        return self.project.text_style.to_dict()

    def relocalize_default_scene_titles(self) -> None:
        for idx, scene in enumerate(self.project.scenes, start=1):
            scene.title = localize_scene_title(scene.title, idx)


    def relocalize_default_project_name(self) -> None:
        self.project.project_name = localize_project_name(self.project.project_name)
