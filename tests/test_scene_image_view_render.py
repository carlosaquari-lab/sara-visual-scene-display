import sys
import tkinter as tk
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import HotspotData, Scene
from app.services.scene_image_view_service import SceneImageViewService, hotspot_caption_top


def _png(path: Path, size: tuple[int, int] = (80, 60), color: tuple[int, int, int] = (40, 90, 140)) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, format="PNG")
    return str(path)


def _scene_with_hotspot() -> Scene:
    return Scene(
        id="scene_1",
        title="Hotspot Scene",
        hotspots=[
            HotspotData(
                id="h1",
                label="Help",
                text="help",
                x=0.25,
                y=0.25,
                width=0.25,
                height=0.25,
                visible_in_design=True,
            )
        ],
    )


def _label():
    root = tk.Tk()
    root.withdraw()
    label = tk.Label(root, width=320, height=240)
    label.pack()
    root.update_idletasks()
    return root, label


def test_load_original_returns_rgba_image_for_valid_png(tmp_path):
    service = SceneImageViewService()
    image_path = _png(tmp_path / "scene.png", size=(32, 24))

    image = service.load_original(image_path)

    assert image is not None
    assert image.mode == "RGBA"
    assert image.size == (32, 24)


def test_scene_image_view_service_exposes_render_method():
    service = SceneImageViewService()

    assert callable(getattr(service, "render", None))


def test_render_design_without_image_returns_placeholder_render_info():
    service = SceneImageViewService()
    root, label = _label()
    try:
        scene_original, scene_photo, render_info = service.render(
            Scene(id="scene_1", title="Empty"),
            "design",
            label,
        )
    finally:
        root.destroy()

    assert scene_original is None
    assert scene_photo is not None
    assert render_info is not None
    assert render_info["no_scene_image"] is True
    assert render_info["display_width"] > 0
    assert render_info["display_height"] > 0
    assert render_info["image_x"] == 0
    assert render_info["image_y"] == 0


def test_render_user_without_image_returns_empty_result_without_breaking():
    service = SceneImageViewService()
    root, label = _label()
    try:
        scene_original, scene_photo, render_info = service.render(
            Scene(id="scene_1", title="Empty"),
            "user",
            label,
        )
    finally:
        root.destroy()

    assert scene_original is None
    assert scene_photo is None
    assert render_info is None


def test_render_valid_image_returns_original_photo_and_render_info(tmp_path):
    service = SceneImageViewService()
    image_path = _png(tmp_path / "scene.png", size=(64, 48))
    scene = Scene(id="scene_1", title="Image", background_image=image_path)
    root, label = _label()
    try:
        scene_original, scene_photo, render_info = service.render(scene, "design", label)
    finally:
        root.destroy()

    assert scene_original is not None
    assert scene_original.mode == "RGBA"
    assert scene_photo is not None
    assert render_info is not None
    assert render_info["display_width"] > 0
    assert render_info["display_height"] > 0
    assert "image_x" in render_info
    assert "image_y" in render_info


def test_load_original_returns_none_for_missing_image(tmp_path):
    service = SceneImageViewService()

    assert service.load_original(str(tmp_path / "missing.png")) is None


def test_load_original_returns_none_for_empty_or_none_path():
    service = SceneImageViewService()

    assert service.load_original("") is None
    assert service.load_original(None) is None


def test_overlay_hotspots_does_not_break_with_visible_hotspot_in_design_mode():
    service = SceneImageViewService()
    image = Image.new("RGBA", (240, 180), (255, 255, 255, 255))

    result = service._overlay_hotspots(image.copy(), _scene_with_hotspot(), "design", show_hotspots=True)

    assert isinstance(result, Image.Image)
    assert result.size == image.size


def test_overlay_hotspots_respects_show_hotspots_false_without_breaking():
    service = SceneImageViewService()
    image = Image.new("RGBA", (240, 180), (255, 255, 255, 255))

    result = service._overlay_hotspots(image.copy(), _scene_with_hotspot(), "design", show_hotspots=False)

    assert isinstance(result, Image.Image)
    assert result.size == image.size


def test_overlay_hotspots_handles_selected_hotspot_in_user_mode():
    service = SceneImageViewService()
    image = Image.new("RGBA", (240, 180), (255, 255, 255, 255))

    result = service._overlay_hotspots(
        image.copy(),
        _scene_with_hotspot(),
        "user",
        selected_hotspot_id="h1",
        show_hotspots=True,
    )

    assert isinstance(result, Image.Image)
    assert result.size == image.size


def test_overlay_hotspots_handles_preview_rect():
    service = SceneImageViewService()
    image = Image.new("RGBA", (240, 180), (255, 255, 255, 255))
    preview_rect = {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}

    result = service._overlay_hotspots(
        image.copy(),
        Scene(id="scene_1", title="Preview"),
        "design",
        preview_rect=preview_rect,
        show_hotspots=True,
    )

    assert isinstance(result, Image.Image)
    assert result.size == image.size


def test_hotspot_caption_prefers_below_and_falls_back_above():
    assert hotspot_caption_top(top=20, bottom=60, box_h=20, disp_h=120, gap=5) == 65
    assert hotspot_caption_top(top=80, bottom=110, box_h=20, disp_h=120, gap=5) == 55
