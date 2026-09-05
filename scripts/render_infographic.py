#!/usr/bin/env python3
"""Render a semantic page as a cumulative animated infographic (no drawing hand)."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H, FPS = 1920, 1080, 30
FONT_DIRS = (
    Path("C:/Windows/Fonts"),
    Path("/System/Library/Fonts"),
    Path("/usr/share/fonts/opentype/noto"),
    Path("/usr/share/fonts/truetype/noto"),
)


def font(size: int, serif: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = (
        ["simhei.ttf", "msyhbd.ttc", "PingFang.ttc", "STHeiti Medium.ttc", "NotoSansCJK-Bold.ttc"]
        if bold
        else ["simkai.ttf", "simsun.ttc", "PingFang.ttc", "Hiragino Sans GB.ttc", "NotoSansCJK-Regular.ttc"]
        if serif
        else ["msyh.ttc", "simhei.ttf", "PingFang.ttc", "STHeiti Medium.ttc", "NotoSansCJK-Regular.ttc"]
    )
    for directory in FONT_DIRS:
        for name in names:
            path = directory / name
            if path.exists():
                return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def palette(style: str) -> dict[str, tuple[int, int, int]]:
    if style in {"黑金科技发布会风", "赛博霓虹漫画风"}:
        return {"paper": (24, 25, 28), "ink": (239, 232, 211), "muted": (172, 169, 158),
                "accent": (216, 174, 84) if "黑金" in style else (49, 226, 220), "second": (177, 77, 151), "line": (95, 88, 75)}
    if style == "爆款高热吸睛风":
        return {"paper": (252, 224, 66), "ink": (35, 32, 29), "muted": (91, 61, 45),
                "accent": (229, 65, 42), "second": (35, 91, 178), "line": (91, 61, 45)}
    if style == "极简商务涂鸦风":
        return {"paper": (244, 247, 246), "ink": (31, 53, 66), "muted": (93, 111, 113),
                "accent": (34, 104, 170), "second": (38, 137, 116), "line": (173, 188, 187)}
    if style == "极简粗线简笔白板风":
        return {"paper": (253, 252, 248), "ink": (35, 35, 33), "muted": (105, 104, 96),
                "accent": (225, 102, 47), "second": (49, 92, 178), "line": (198, 195, 184)}
    if style == "粗线扁平国风卡通":
        return {"paper": (247, 238, 219), "ink": (55, 48, 40), "muted": (105, 91, 77),
                "accent": (177, 62, 43), "second": (53, 103, 84), "line": (194, 171, 139)}
    if style == "清新治愈手账风":
        return {"paper": (252, 247, 235), "ink": (67, 72, 65), "muted": (115, 119, 105),
                "accent": (214, 121, 111), "second": (111, 145, 111), "line": (205, 194, 174)}
    if style == "复古报纸拼贴风":
        return {"paper": (229, 217, 194), "ink": (43, 40, 35), "muted": (93, 84, 72),
                "accent": (157, 49, 39), "second": (62, 60, 53), "line": (155, 139, 113)}
    if style == "漫画墨线解释风":
        return {"paper": (244, 239, 229), "ink": (36, 35, 31), "muted": (110, 106, 97),
                "accent": (207, 105, 62), "second": (79, 120, 149), "line": (185, 177, 163)}
    if style == "3D黏土趣味风":
        return {"paper": (250, 239, 215), "ink": (65, 57, 50), "muted": (116, 102, 90),
                "accent": (222, 104, 76), "second": (53, 145, 135), "line": (205, 181, 145)}
    return {"paper": (246, 241, 229), "ink": (43, 48, 47), "muted": (101, 99, 91),
            "accent": (177, 68, 52), "second": (49, 72, 78), "line": (190, 181, 163)}


def ease(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1 - (1 - value) ** 3


def text_size(draw: ImageDraw.ImageDraw, text: str, text_font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=text_font)
    return box[2] - box[0], box[3] - box[1]


def layer() -> Image.Image:
    return Image.new("RGBA", (W, H))


def paste_faded(canvas: Image.Image, item: Image.Image, alpha: float, x_shift: int = 0, y_shift: int = 0) -> None:
    if alpha <= 0:
        return
    moved = Image.new("RGBA", canvas.size)
    moved.alpha_composite(item, (x_shift, y_shift))
    moved.putalpha(moved.getchannel("A").point(lambda value: int(value * min(1.0, alpha))))
    canvas.alpha_composite(moved)


def base_page(scene: dict[str, Any], colors: dict[str, tuple[int, int, int]]) -> Image.Image:
    image = Image.new("RGBA", (W, H), colors["paper"] + (255,))
    draw = ImageDraw.Draw(image)
    wash = Image.new("RGBA", (W, H))
    wash_draw = ImageDraw.Draw(wash)
    wash_draw.polygon(((-120, 820), (310, 690), (570, 1080), (-120, 1080)), fill=colors["line"] + (15,))
    wash_draw.polygon(((1380, -80), (1940, -80), (1940, 330), (1670, 230)), fill=colors["second"] + (10,))
    wash_draw.polygon(((670, 390), (1110, 260), (1370, 660), (1010, 850), (590, 680)), fill=colors["line"] + (8,))
    image.alpha_composite(wash.filter(ImageFilter.GaussianBlur(55)))
    draw.rectangle((58, 51, 67, 116), fill=colors["accent"])
    series = str(scene.get("series_title") or "动态知识解说")[:30]
    draw.text((94, 48), series, font=font(46, serif=True, bold=True), fill=colors["ink"])
    draw.line((58, 133, 1862, 133), fill=colors["line"], width=2)
    chapter = str(scene.get("chapter_title") or "本章要点")[:24]
    chapter_font = font(30, serif=True, bold=True)
    width, _ = text_size(draw, chapter, chapter_font)
    draw.text(((W - width) // 2, 164), chapter, font=chapter_font, fill=colors["ink"])
    draw.line(((W-width)//2-34, 210, (W+width)//2+34, 210), fill=colors["line"], width=1)
    return image


def art_layer(path: Path, layout_name: str) -> Image.Image:
    source = Image.open(path).convert("RGB")
    source = ImageEnhance.Color(source).enhance(.72)
    source = ImageEnhance.Contrast(source).enhance(.92)
    if layout_name in {"focus", "summary", "comparison"}:
        bounds = (1010, 285, 1835, 920)
    elif layout_name in {"overview", "cycle"}:
        bounds = (600, 305, 1320, 865)
    else:
        bounds = (440, 300, 1480, 730)
    max_w, max_h = bounds[2] - bounds[0], bounds[3] - bounds[1]
    source.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    feather = max(26, min(source.size) // 12)
    yy, xx = np.mgrid[0:source.height, 0:source.width]
    distance = np.minimum.reduce((xx, yy, source.width - 1 - xx, source.height - 1 - yy))
    mask_array = np.clip(distance / feather * 255, 0, 255).astype(np.uint8)
    mask = Image.fromarray(mask_array, mode="L").filter(ImageFilter.GaussianBlur(feather / 5))
    result = layer()
    x = bounds[0] + (max_w - source.width) // 2
    y = bounds[1] + (max_h - source.height) // 2
    result.paste(source, (x, y), mask)
    return result


def title_layer(scene: dict[str, Any], colors: dict[str, tuple[int, int, int]]) -> Image.Image:
    result = layer()
    draw = ImageDraw.Draw(result)
    title = str(scene.get("page_title") or scene.get("key_text") or "核心观点")[:22]
    title_font = font(54, serif=True, bold=True)
    width, _ = text_size(draw, title, title_font)
    draw.text(((W-width)//2, 234), title, font=title_font, fill=colors["accent"])
    return result


def node_layer(text: str, x: int, y: int, colors: dict[str, tuple[int, int, int]], index: int | None = None, align: str = "center") -> Image.Image:
    result = layer()
    draw = ImageDraw.Draw(result)
    node_font = font(30, bold=True)
    text = text[:12]
    width, height = text_size(draw, text, node_font)
    tx = x - width // 2 if align == "center" else x - width if align == "right" else x
    if index is not None:
        draw.ellipse((tx - 52, y - 3, tx - 16, y + 33), fill=colors["second"] if index % 2 else colors["accent"])
        number_font = font(17, bold=True)
        number = str(index)
        nw, _ = text_size(draw, number, number_font)
        draw.text((tx - 34 - nw//2, y + 4), number, font=number_font, fill=colors["paper"])
    draw.text((tx, y), text, font=node_font, fill=colors["ink"])
    draw.line((tx, y + height + 11, tx + width, y + height + 11), fill=colors["line"], width=2)
    return result


def connector(start: tuple[int, int], end: tuple[int, int], colors: dict[str, tuple[int, int, int]], arrow: bool = True) -> Image.Image:
    result = layer()
    draw = ImageDraw.Draw(result)
    draw.line((*start, *end), fill=colors["second"], width=4)
    if arrow:
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = max(1.0, (dx*dx + dy*dy) ** .5)
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        left = (int(end[0]-ux*18+px*8), int(end[1]-uy*18+py*8))
        right = (int(end[0]-ux*18-px*8), int(end[1]-uy*18-py*8))
        draw.polygon((end, left, right), fill=colors["second"])
    return result


def layout_elements(scene: dict[str, Any], colors: dict[str, tuple[int, int, int]]) -> list[Image.Image]:
    layout_name = str(scene.get("layout_type") or "focus")
    nodes = [str(value)[:12] for value in (scene.get("nodes") or [])][:5]
    if not nodes:
        nodes = [str(scene.get("key_text") or "本页重点")[:12]]
    elements: list[Image.Image] = [title_layer(scene, colors)]
    if layout_name in {"flow", "cause", "timeline"}:
        xs = [260 + round(index * 1400 / max(1, len(nodes) - 1)) for index in range(len(nodes))]
        y = 820
        for index, (x, text) in enumerate(zip(xs, nodes), 1):
            if index > 1:
                elements.append(connector((xs[index-2] + 70, y + 22), (x - 85, y + 22), colors))
            elements.append(node_layer(text, x, y, colors, index))
    elif layout_name == "comparison":
        split = max(1, (len(nodes) + 1) // 2)
        for index, text in enumerate(nodes):
            left = index < split
            x = 210 if left else 650
            y = 405 + (index if left else index - split) * 145
            elements.append(node_layer(text, x, y, colors, index + 1, "left"))
        elements.insert(1, connector((620, 385), (620, 835), colors, False))
    elif layout_name == "layers":
        for index, text in enumerate(nodes, 1):
            elements.append(node_layer(text, 165 + (index - 1) * 55, 380 + (index - 1) * 115, colors, index, "left"))
    elif layout_name in {"overview", "cycle"}:
        positions = [(330, 390), (1570, 390), (280, 775), (1620, 775), (960, 910)]
        center = (960, 620)
        for index, (text, position) in enumerate(zip(nodes, positions), 1):
            elements.append(connector(center, position, colors, layout_name != "cycle"))
            elements.append(node_layer(text, position[0], position[1], colors, index))
    elif layout_name == "summary":
        for index, text in enumerate(nodes, 1):
            elements.append(node_layer(text, 155, 370 + (index - 1) * 118, colors, index, "left"))
    else:
        for index, text in enumerate(nodes, 1):
            y = 410 + (index - 1) * 145
            elements.append(node_layer(text, 155, y, colors, index, "left"))
            elements.append(connector((520, y + 22), (905, 520 + (index - 1) * 50), colors))
    conclusion_text = str(scene.get("conclusion") or "").strip()[:18]
    if conclusion_text:
        result = layer()
        draw = ImageDraw.Draw(result)
        conclusion_font = font(31, serif=True, bold=True)
        width, _ = text_size(draw, conclusion_text, conclusion_font)
        x = (W - width) // 2
        draw.line((x - 45, 995, x - 15, 995), fill=colors["accent"], width=5)
        draw.text((x, 974), conclusion_text, font=conclusion_font, fill=colors["accent"])
        draw.line((x + width + 15, 995, x + width + 45, 995), fill=colors["accent"], width=5)
        elements.append(result)
    return elements


def render(image_path: Path, scene_path: Path, output: Path, duration_ms: int) -> None:
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    style = str(scene.get("render_style") or "暖米黄素描白板风")
    colors = palette(style)
    layout_name = str(scene.get("layout_type") or "focus")
    base = base_page(scene, colors)
    art = art_layer(image_path, layout_name)
    elements = layout_elements(scene, colors)
    total_frames = max(FPS, round(duration_ms / 1000 * FPS))
    spacing = min(.11, .62 / max(1, len(elements)))
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", str(output)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE)
    assert process.stdin is not None
    try:
        for frame_index in range(total_frames):
            progress = frame_index / max(1, total_frames - 1)
            canvas = base.copy()
            art_alpha = ease((progress - .08) / .14)
            paste_faded(canvas, art, art_alpha, round(42 * (1 - art_alpha)), round(12 * (1 - art_alpha)))
            for index, item in enumerate(elements):
                alpha = ease((progress - (.04 + index * spacing)) / .085)
                paste_faded(canvas, item, alpha, 0, round(16 * (1 - alpha)))
            process.stdin.write(np.asarray(canvas.convert("RGB")).tobytes())
    finally:
        process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("信息图视频编码失败")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("scene", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--duration-ms", type=int, required=True)
    args = parser.parse_args()
    render(args.image, args.scene, args.output, args.duration_ms)


if __name__ == "__main__":
    main()
