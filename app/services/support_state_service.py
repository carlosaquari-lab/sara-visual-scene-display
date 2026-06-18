from __future__ import annotations


def support_has_content(cell) -> bool:
    if cell is None:
        return False
    try:
        return bool((getattr(cell, "text", "") or "").strip() or getattr(cell, "image_path", "") or getattr(cell, "audio_path", ""))
    except Exception:
        return False


def scene_has_supports(scene) -> bool:
    try:
        supports = list(getattr(scene, "supports", []) or [])
    except Exception:
        supports = []
    return any(
        bool(getattr(s, "visible", False)) or support_has_content(s)
        for s in supports
    )


def project_has_any_supports(project) -> bool:
    try:
        scenes = list(getattr(project, "scenes", []) or [])
    except Exception:
        scenes = []
    for scene in scenes:
        try:
            supports = list(getattr(scene, "supports", []) or [])
        except Exception:
            supports = []
        if any(bool(getattr(s, "visible", False)) or support_has_content(s) for s in supports):
            return True
    return False


def support_counts(scene, strip_on: bool, max_items: int) -> dict:
    supports = list(getattr(scene, "supports", []) or [])
    configured = 0
    marked_visible = 0
    for idx in range(max_items):
        support = supports[idx] if idx < len(supports) else None
        if support_has_content(support):
            configured += 1
        if strip_on and support is not None and bool(getattr(support, "visible", False)):
            marked_visible += 1
    return {
        "support_slots_total": max_items,
        "support_slots_configured": configured,
        "support_slots_presented": marked_visible,
        "support_strip_enabled": int(strip_on),
    }
