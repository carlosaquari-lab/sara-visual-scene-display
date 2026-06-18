from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont, ImageTk

from app import config
from app.i18n import tr
from app.services.hotspot_geometry_service import (
    hotspot_handle_hit_test,
    hotspot_hit_test,
    hotspot_rect_px,
)


def _safe_color(value: str | None, fallback: str) -> str:
    text = str(value or "").strip()
    if len(text) == 7 and text.startswith("#"):
        return text
    return fallback


def _hotspot_font(size: int):
    try:
        size = max(8, min(int(size), 32))
    except Exception:
        size = 16
    for name in ("DejaVuSans-Bold.ttf", "Arial.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def hotspot_caption_top(top: int, bottom: int, box_h: int, disp_h: int, gap: int) -> int:
    """Place a hotspot caption below when possible, otherwise above."""
    below_top = bottom + gap
    if below_top + box_h <= disp_h - 1:
        return below_top
    return top - gap - box_h


class SceneImageViewService:
    """Handles scene image preview loading, scaling and hotspot overlay rendering."""

    def load_original(self, background_image: str | None):
        if background_image and os.path.exists(background_image):
            try:
                return Image.open(background_image).convert("RGBA")
            except Exception:
                return None
        return None

    def hotspot_hit_test(self, hotspots, render_info: dict | None, event_x: int, event_y: int):
        return hotspot_hit_test(hotspots, render_info, event_x, event_y)

    def hotspot_rect_px(self, hotspot, render_info: dict | None):
        return hotspot_rect_px(hotspot, render_info)

    def hotspot_handle_hit_test(self, hotspot, render_info: dict | None, event_x: int, event_y: int):
        return hotspot_handle_hit_test(hotspot, render_info, event_x, event_y)

    def _overlay_hotspots(self, image: Image.Image, scene, current_mode: str, preview_rect: dict | None = None, selected_hotspot_id: str = "", show_hotspots: bool = True) -> Image.Image:
        draw = ImageDraw.Draw(image, "RGBA")
        disp_w, disp_h = image.size
        if show_hotspots:
            for hotspot in list(getattr(scene, "hotspots", []) or []):
                visible = current_mode == "design" or bool(getattr(hotspot, "visible_in_design", True))
                if not visible:
                    continue
                left = int(float(getattr(hotspot, "x", 0.0)) * disp_w)
                top = int(float(getattr(hotspot, "y", 0.0)) * disp_h)
                width = max(18, int(float(getattr(hotspot, "width", 0.0)) * disp_w))
                height = max(18, int(float(getattr(hotspot, "height", 0.0)) * disp_h))
                right = min(disp_w - 1, left + width)
                bottom = min(disp_h - 1, top + height)
                is_selected = selected_hotspot_id and str(getattr(hotspot, "id", "")) == str(selected_hotspot_id)
                # 0.1.14: in user mode, only the active hotspot is drawn.
                # When the timer clears selected_hotspot_id, both the label and
                # the blue rectangle disappear.
                if current_mode != "design" and not is_selected:
                    continue
                outline = (44, 123, 229, 255) if not is_selected else (22, 86, 191, 255)
                draw.rounded_rectangle((left, top, right, bottom), radius=10, outline=outline, width=3)

                label_text = str(getattr(hotspot, "label", "") or getattr(hotspot, "text", "") or "").strip().upper()
                if label_text and (current_mode == "design" or is_selected):
                    font = _hotspot_font(getattr(hotspot, "label_font_size", 16))
                    bg_color = _safe_color(getattr(hotspot, "label_bg_color", "#FFFFFF"), "#FFFFFF")
                    fg_color = _safe_color(getattr(hotspot, "label_fg_color", "#000000"), "#000000")
                    text_bbox = draw.textbbox((0, 0), label_text, font=font)
                    text_w = max(1, text_bbox[2] - text_bbox[0])
                    text_h = max(1, text_bbox[3] - text_bbox[1])
                    # Balanced label: enough internal padding and a clearly
                    # visible external gap. The previous value still looked too
                    # close to the hotspot line. The label is now separated from
                    # the selected border/handles by approximately one full label
                    # height, so the empty space above the label feels balanced
                    # with the space below and the text no longer appears attached
                    # to the blue rectangle.
                    pad_x, pad_y = 8, 5
                    box_w = min(text_w + 2 * pad_x, max(28, right - left - 4))
                    box_h = text_h + 2 * pad_y
                    box_left = left + ((right - left) - box_w) // 2
                    box_left = max(2, min(box_left, disp_w - box_w - 2))
                    handle_clearance = 8 if (current_mode == "design" and is_selected) else 0
                    label_gap = 5 + handle_clearance
                    # Captions always remain outside the hotspot: below is
                    # preferred, with above as the only fallback.
                    box_top = hotspot_caption_top(top, bottom, box_h, disp_h, label_gap)
                    box_bottom = box_top + box_h
                    outline_color = (22, 86, 191, 255) if is_selected else (44, 123, 229, 255)
                    draw.rounded_rectangle(
                        (box_left, box_top, box_left + box_w, box_bottom),
                        radius=5,
                        fill=bg_color,
                        outline=outline_color,
                        width=2,
                    )
                    # Center the label text visually inside the white box.
                    # Pillow textbbox can return a bbox whose top is not zero,
                    # so using only text_h leaves the text slightly low. We
                    # compensate with the bbox origin to keep the white space
                    # above and below the text as balanced as possible.
                    tx = box_left + ((box_w - text_w) // 2) - text_bbox[0]
                    ty = box_top + ((box_h - text_h) // 2) - text_bbox[1]
                    draw.text((tx, ty), label_text, fill=fg_color, font=font)

                if current_mode == "design" and is_selected:
                    handle_r = 5
                    for hx, hy in ((left, top), (right, top), (left, bottom), (right, bottom)):
                        draw.ellipse((hx-handle_r, hy-handle_r, hx+handle_r, hy+handle_r), outline=(22, 86, 191, 255), width=2, fill=(255,255,255,255))
        if preview_rect:
            left = int(float(preview_rect.get("x", 0.0)) * disp_w)
            top = int(float(preview_rect.get("y", 0.0)) * disp_h)
            width = max(8, int(float(preview_rect.get("width", 0.0)) * disp_w))
            height = max(8, int(float(preview_rect.get("height", 0.0)) * disp_h))
            right = min(disp_w - 1, left + width)
            bottom = min(disp_h - 1, top + height)
            draw.rounded_rectangle((left, top, right, bottom), radius=10, outline=(44, 123, 229, 255), width=2)
        return image

    def render(self, scene, current_mode: str, label, current_original=None, preview_rect: dict | None = None, selected_hotspot_id: str = "", show_hotspots: bool = True):
        scene_original = self.load_original(getattr(scene, "background_image", None))
        width = max(min(label.winfo_width(), config.MAX_SCENE_IMAGE_DISPLAY[0]), 220)
        height = max(min(label.winfo_height(), config.MAX_SCENE_IMAGE_DISPLAY[1]), 220)

        if scene_original is None:
            if current_mode == "design":
                # Sara 0.1.28: v0.1.18 base + large grey central plus.
                # The plus is part of the placeholder image, not a Tk overlay.
                placeholder = Image.new("RGBA", (width, height), (242, 242, 242, 255))
                draw = ImageDraw.Draw(placeholder, "RGBA")
                msg = tr("scene_no_image_click")
                plus_size = 92
                plus_w = plus_h = plus_size
                plus_x = (width - plus_w) // 2
                plus_y = max(18, (height // 2) - plus_h - 6)
                icon_path = config.ASSETS_ICONS_DIR / "hotspot_add.png"
                pasted = False
                try:
                    if icon_path.exists():
                        plus_icon = Image.open(str(icon_path)).convert("RGBA")
                        plus_icon.thumbnail((plus_size, plus_size), Image.LANCZOS)
                        px = plus_icon.load()
                        for yy in range(plus_icon.height):
                            for xx in range(plus_icon.width):
                                r, g, b, a = px[xx, yy]
                                if a == 0:
                                    continue
                                if max(r, g, b) > 100:
                                    px[xx, yy] = (170, 170, 170, a)
                                elif max(r, g, b) > 25 and abs(r - g) + abs(g - b) > 20:
                                    px[xx, yy] = (90, 90, 90, a)
                        plus_w, plus_h = plus_icon.width, plus_icon.height
                        plus_x = (width - plus_w) // 2
                        plus_y = max(18, (height // 2) - plus_h - 6)
                        placeholder.paste(plus_icon, (plus_x, plus_y), plus_icon)
                        pasted = True
                except Exception:
                    pasted = False
                if not pasted:
                    cx = width // 2
                    cy = max(18 + plus_size // 2, (height // 2) - 6)
                    half_arm = plus_size // 3
                    line_w = max(8, plus_size // 9)
                    draw.ellipse((cx - plus_size//2, cy - plus_size//2, cx + plus_size//2, cy + plus_size//2), fill=(170,170,170,255))
                    draw.line((cx - half_arm, cy, cx + half_arm, cy), fill=(0,0,0,255), width=line_w)
                    draw.line((cx, cy - half_arm, cx, cy + half_arm), fill=(0,0,0,255), width=line_w)
                    plus_x = cx - plus_size // 2
                    plus_y = cy - plus_size // 2
                    plus_w = plus_h = plus_size

                try:
                    font = ImageFont.truetype("Arial.ttf", 11)
                    font_bold = ImageFont.truetype("Arial.ttf", 12)
                except Exception:
                    font = ImageFont.load_default()
                    font_bold = font
                lines = [line for line in msg.split("\n") if line.strip()]
                total_h = 0
                metrics = []
                for i, line in enumerate(lines):
                    f = font_bold if i == 0 else font
                    bbox = draw.textbbox((0, 0), line, font=f)
                    line_h = bbox[3] - bbox[1]
                    metrics.append((line, f, bbox, line_h))
                    total_h += line_h + 4
                y = plus_y + plus_h + 12
                if y + total_h > height - 14:
                    y = max(14, height - total_h - 14)
                for line, f, bbox, line_h in metrics:
                    tx = (width - (bbox[2] - bbox[0])) // 2
                    draw.text((tx, y), line, fill=(25, 25, 25, 255), font=f)
                    y += line_h + 4
                scene_photo = ImageTk.PhotoImage(placeholder)
                label.configure(image=scene_photo, text="")
                render_info = {
                    "label_width": width,
                    "label_height": height,
                    "display_width": width,
                    "display_height": height,
                    "image_x": 0,
                    "image_y": 0,
                    "no_scene_image": True,
                    "empty_plus_size": plus_size,
                }
                return None, scene_photo, render_info
            msg = tr("scene_no_image")
            label.configure(image="", text=msg)
            return None, None, None

        image = scene_original.copy()
        image.thumbnail((max(width - 12, 120), max(height - 12, 120)), Image.LANCZOS)
        image = self._overlay_hotspots(image, scene, current_mode, preview_rect=preview_rect, selected_hotspot_id=selected_hotspot_id, show_hotspots=show_hotspots)
        scene_photo = ImageTk.PhotoImage(image)
        label.configure(image=scene_photo, text="")
        render_info = {
            "label_width": width,
            "label_height": height,
            "display_width": image.width,
            "display_height": image.height,
            "image_x": max(0, (width - image.width) // 2),
            "image_y": max(0, (height - image.height) // 2),
        }
        return scene_original, scene_photo, render_info
