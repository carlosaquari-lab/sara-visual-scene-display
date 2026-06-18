from __future__ import annotations

from app.i18n import tr
from app.models import CellData, HotspotData, Scene, StoryProject, default_scene, normalize_scene, normalize_supports


def create_scene(project: StoryProject, title: str | None = None) -> Scene:
    scene = default_scene(len(project.scenes) + 1, project.grid_rows, project.grid_cols)
    if title:
        scene.title = title
    project.scenes.append(scene)
    return scene


def _copy_scene_title(project: StoryProject, base_title: str) -> str:
    base = (base_title or tr("scene_base")).strip()
    suffix = tr("copy_suffix")
    candidate = f"{base} ({suffix})"
    existing = {((scene.title or "").strip().lower()) for scene in project.scenes}
    if candidate.lower() not in existing:
        return candidate
    n = 2
    while True:
        candidate = f"{base} ({suffix} {n})"
        if candidate.lower() not in existing:
            return candidate
        n += 1


def duplicate_scene(project: StoryProject, index: int) -> int:
    source = project.scenes[index]
    clone = default_scene(len(project.scenes) + 1, project.grid_rows, project.grid_cols)
    clone.title = _copy_scene_title(project, source.title)
    clone.background_image = source.background_image
    clone.scene_audio = source.scene_audio
    clone.cells = [CellData.from_dict(cell.to_dict()) for cell in source.cells[: project.total_cells]]
    clone.supports = [CellData.from_dict(support.to_dict()) for support in list(getattr(source, "supports", []) or [])]
    clone.hotspots = [HotspotData.from_dict(hotspot.to_dict()) for hotspot in list(getattr(source, "hotspots", []) or [])]
    normalize_scene(clone, project.grid_rows, project.grid_cols)
    normalize_supports(clone)
    project.scenes.insert(index + 1, clone)
    return index + 1


def remove_scene(project: StoryProject, index: int) -> int:
    if len(project.scenes) <= 1:
        project.scenes[0] = default_scene(1, project.grid_rows, project.grid_cols)
        return 0
    del project.scenes[index]
    return max(0, min(index, len(project.scenes) - 1))


def apply_grid_to_project(project: StoryProject, rows: int, cols: int) -> None:
    project.grid_rows = int(rows)
    project.grid_cols = int(cols)
    for scene in project.scenes:
        normalize_scene(scene, project.grid_rows, project.grid_cols)


def move_scene(project: StoryProject, from_index: int, to_index: int) -> int:
    if not project.scenes:
        return 0
    from_index = max(0, min(int(from_index), len(project.scenes) - 1))
    to_index = max(0, min(int(to_index), len(project.scenes) - 1))
    if from_index == to_index:
        return from_index
    scene = project.scenes.pop(from_index)
    project.scenes.insert(to_index, scene)
    return to_index
