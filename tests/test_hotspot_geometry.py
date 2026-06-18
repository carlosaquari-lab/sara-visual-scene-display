import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import HotspotData
from app.services.hotspot_geometry_service import hotspot_overlaps_any, hotspot_rects_overlap
from app.services.scene_image_view_service import SceneImageViewService


def _render_info(width: int = 1000, height: int = 600, image_x: int = 0, image_y: int = 0) -> dict:
    return {
        "display_width": width,
        "display_height": height,
        "image_x": image_x,
        "image_y": image_y,
    }


def test_hotspot_rect_px_converts_normalized_coordinates_to_pixels():
    service = SceneImageViewService()
    hotspot = HotspotData(id="h1", x=0.25, y=0.5, width=0.2, height=0.1)

    assert service.hotspot_rect_px(hotspot, _render_info()) == (250, 300, 200, 60)


def test_hotspot_hit_test_inside_outside_and_image_offset():
    service = SceneImageViewService()
    hotspot = HotspotData(id="h1", x=0.25, y=0.5, width=0.2, height=0.1)
    info = _render_info(image_x=20, image_y=30)

    assert service.hotspot_hit_test([hotspot], info, 270, 330) is hotspot
    assert service.hotspot_hit_test([hotspot], info, 10, 330) is None
    assert service.hotspot_hit_test([hotspot], info, 100, 100) is None


def test_hotspot_hit_test_prefers_topmost_last_hotspot_when_overlapping():
    service = SceneImageViewService()
    bottom = HotspotData(id="bottom", x=0.1, y=0.1, width=0.5, height=0.5)
    top = HotspotData(id="top", x=0.2, y=0.2, width=0.5, height=0.5)

    assert service.hotspot_hit_test([bottom, top], _render_info(), 300, 200) is top


def test_hotspot_handle_hit_test_detects_corner_handles():
    service = SceneImageViewService()
    hotspot = HotspotData(id="h1", x=0.25, y=0.5, width=0.2, height=0.1)
    info = _render_info(image_x=20, image_y=30)

    assert service.hotspot_handle_hit_test(hotspot, info, 270, 330) == "nw"
    assert service.hotspot_handle_hit_test(hotspot, info, 470, 330) == "ne"
    assert service.hotspot_handle_hit_test(hotspot, info, 270, 390) == "sw"
    assert service.hotspot_handle_hit_test(hotspot, info, 470, 390) == "se"
    assert service.hotspot_handle_hit_test(hotspot, info, 350, 350) is None


def test_hotspot_handle_hit_test_accepts_near_corner_outside_rect():
    service = SceneImageViewService()
    hotspot = HotspotData(id="h1", x=0.25, y=0.5, width=0.2, height=0.1)
    info = _render_info(image_x=20, image_y=30)

    assert service.hotspot_handle_hit_test(hotspot, info, 260, 320) == "nw"
    assert service.hotspot_handle_hit_test(hotspot, info, 480, 400) == "se"


def test_hotspot_geometry_returns_none_for_invalid_render_info():
    service = SceneImageViewService()
    hotspot = HotspotData(id="h1", x=0.25, y=0.5, width=0.2, height=0.1)

    assert service.hotspot_rect_px(hotspot, None) is None
    assert service.hotspot_hit_test([hotspot], None, 100, 100) is None
    assert service.hotspot_handle_hit_test(hotspot, None, 100, 100) is None

    zero_width = _render_info(width=0, height=600)
    zero_height = _render_info(width=1000, height=0)
    assert service.hotspot_rect_px(hotspot, zero_width) is None
    assert service.hotspot_rect_px(hotspot, zero_height) is None
    assert service.hotspot_hit_test([hotspot], zero_width, 100, 100) is None
    assert service.hotspot_hit_test([hotspot], zero_height, 100, 100) is None
    assert service.hotspot_handle_hit_test(hotspot, zero_width, 100, 100) is None
    assert service.hotspot_handle_hit_test(hotspot, zero_height, 100, 100) is None


def test_hotspot_rect_px_applies_minimum_editable_size():
    service = SceneImageViewService()
    hotspot = HotspotData(id="tiny", x=0.1, y=0.2, width=0.001, height=0.001)

    assert service.hotspot_rect_px(hotspot, _render_info(width=100, height=80)) == (10, 16, 18, 18)


def test_hotspot_overlap_requires_positive_intersection_area():
    first = HotspotData(id="first", x=0.1, y=0.1, width=0.2, height=0.2)
    overlapping = HotspotData(id="overlapping", x=0.2, y=0.2, width=0.2, height=0.2)
    touching = HotspotData(id="touching", x=0.3, y=0.1, width=0.2, height=0.2)

    assert hotspot_rects_overlap(first, overlapping) is True
    assert hotspot_rects_overlap(first, touching) is False


def test_hotspot_overlaps_any_ignores_same_hotspot():
    first = HotspotData(id="first", x=0.1, y=0.1, width=0.2, height=0.2)
    other = HotspotData(id="other", x=0.15, y=0.15, width=0.2, height=0.2)

    assert hotspot_overlaps_any(first, [first]) is False
    assert hotspot_overlaps_any(first, [first, other]) is True
