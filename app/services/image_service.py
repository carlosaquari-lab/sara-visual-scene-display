from __future__ import annotations

from typing import Tuple

from PIL import Image

from app import config


def cell_render_preset(mode: str) -> tuple[float, float]:
    if mode == "user":
        return config.CELL_MARGIN_RATIO_USER, config.CELL_MAX_UPSCALE_USER
    return config.CELL_MARGIN_RATIO_DESIGN, config.CELL_MAX_UPSCALE_DESIGN


def fitted_image_for_cell(src: Image.Image, width: int, height: int, mode: str, fit_mode: str = "contain") -> Image.Image:
    """Return an image fitted to the available cell/support area.

    fit_mode="contain" preserves the full image inside the cell.
    fit_mode="cover" fills the available area and crops the excess from the
    centre. SaraB uses cover for the visual-support column so support images do
    not appear as small thumbnails floating inside a large card.
    """
    margin_ratio, max_upscale = cell_render_preset(mode)
    fit_mode = str(fit_mode or "contain").lower().strip()
    # Supports use cover mode and need less internal margin to fill the card.
    if fit_mode == "cover":
        margin_ratio = min(margin_ratio, 0.025)
    avail_w = max(int(width * (1.0 - margin_ratio * 2)), 48)
    avail_h = max(int(height * (1.0 - margin_ratio * 2)), 48)
    image = src.copy()
    sw, sh = image.size
    if sw <= 0 or sh <= 0:
        return image

    if fit_mode == "cover":
        scale = max(avail_w / max(sw, 1), avail_h / max(sh, 1))
        scale = min(scale, max_upscale) if scale > 1.0 else scale
        new_w = max(1, int(sw * scale))
        new_h = max(1, int(sh * scale))
        image = image.resize((new_w, new_h), Image.LANCZOS)
        left = max(0, (new_w - avail_w) // 2)
        top = max(0, (new_h - avail_h) // 2)
        image = image.crop((left, top, min(left + avail_w, new_w), min(top + avail_h, new_h)))
        return image

    image.thumbnail((avail_w, avail_h), Image.LANCZOS)
    iw, ih = image.size
    upscale = min(avail_w / max(iw, 1), avail_h / max(ih, 1), max_upscale)
    if upscale > 1.03:
        new_size = (max(1, int(iw * upscale)), max(1, int(ih * upscale)))
        new_size = (min(new_size[0], avail_w), min(new_size[1], avail_h))
        image = image.resize(new_size, Image.LANCZOS)
    return image


def scene_preview_size() -> Tuple[int, int]:
    return config.MAX_SCENE_IMAGE_DISPLAY
