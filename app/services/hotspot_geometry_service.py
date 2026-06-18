from __future__ import annotations


def hotspot_rect_px(hotspot, render_info: dict | None):
    if not render_info:
        return None
    display_w = int(render_info.get("display_width", 0))
    display_h = int(render_info.get("display_height", 0))
    if display_w <= 0 or display_h <= 0:
        return None
    left = int(float(getattr(hotspot, "x", 0.0)) * display_w)
    top = int(float(getattr(hotspot, "y", 0.0)) * display_h)
    width = max(18, int(float(getattr(hotspot, "width", 0.0)) * display_w))
    height = max(18, int(float(getattr(hotspot, "height", 0.0)) * display_h))
    return left, top, width, height


def hotspot_hit_test(hotspots, render_info: dict | None, event_x: int, event_y: int):
    if not render_info:
        return None
    image_x = int(render_info.get("image_x", 0))
    image_y = int(render_info.get("image_y", 0))
    display_w = int(render_info.get("display_width", 0))
    display_h = int(render_info.get("display_height", 0))
    if display_w <= 0 or display_h <= 0:
        return None
    local_x = event_x - image_x
    local_y = event_y - image_y
    if local_x < 0 or local_y < 0 or local_x > display_w or local_y > display_h:
        return None
    for hotspot in reversed(list(hotspots or [])):
        left = int(float(getattr(hotspot, "x", 0.0)) * display_w)
        top = int(float(getattr(hotspot, "y", 0.0)) * display_h)
        width = int(float(getattr(hotspot, "width", 0.0)) * display_w)
        height = int(float(getattr(hotspot, "height", 0.0)) * display_h)
        if left <= local_x <= left + width and top <= local_y <= top + height:
            return hotspot
    return None


def hotspot_handle_hit_test(hotspot, render_info: dict | None, event_x: int, event_y: int):
    if not render_info or hotspot is None:
        return None
    image_x = int(render_info.get("image_x", 0))
    image_y = int(render_info.get("image_y", 0))
    rect = hotspot_rect_px(hotspot, render_info)
    if rect is None:
        return None
    left, top, width, height = rect
    right = left + width
    bottom = top + height
    local_x = event_x - image_x
    local_y = event_y - image_y
    hs = 12
    handles = {
        "nw": (left, top),
        "ne": (right, top),
        "sw": (left, bottom),
        "se": (right, bottom),
    }
    for name, (hx, hy) in handles.items():
        if abs(local_x - hx) <= hs and abs(local_y - hy) <= hs:
            return name
    return None


def hotspot_rects_overlap(first, second) -> bool:
    """Return True when two normalized hotspot rectangles overlap by area."""
    first_left = float(getattr(first, "x", 0.0))
    first_top = float(getattr(first, "y", 0.0))
    first_right = first_left + float(getattr(first, "width", 0.0))
    first_bottom = first_top + float(getattr(first, "height", 0.0))

    second_left = float(getattr(second, "x", 0.0))
    second_top = float(getattr(second, "y", 0.0))
    second_right = second_left + float(getattr(second, "width", 0.0))
    second_bottom = second_top + float(getattr(second, "height", 0.0))

    epsilon = 1e-9
    overlap_width = min(first_right, second_right) - max(first_left, second_left)
    overlap_height = min(first_bottom, second_bottom) - max(first_top, second_top)
    return overlap_width > epsilon and overlap_height > epsilon


def hotspot_overlaps_any(hotspot, hotspots, *, exclude_id: str = "") -> bool:
    """Return True when a hotspot overlaps any other hotspot in the collection."""
    hotspot_id = str(getattr(hotspot, "id", "") or "")
    excluded = str(exclude_id or hotspot_id)
    for other in list(hotspots or []):
        if other is hotspot:
            continue
        if excluded and str(getattr(other, "id", "") or "") == excluded:
            continue
        if hotspot_rects_overlap(hotspot, other):
            return True
    return False
