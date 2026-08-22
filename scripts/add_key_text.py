from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont, ImageStat


FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/msyhbd.ttc"),
    Path("C:/Windows/Fonts/msyh.ttc"),
    Path("C:/Windows/Fonts/simhei.ttf"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
)


def clean_key_text(value: str, limit: int = 10) -> str:
    text = re.sub(r"[\s\r\n]+", "", str(value))
    text = re.sub(r"^[，。！？!?；;：:、·—\-]+|[，。！？!?；;：:、·—\-]+$", "", text)
    return text[:limit]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = next((candidate for candidate in FONT_CANDIDATES if candidate.exists()), None)
    return ImageFont.truetype(str(path), size) if path else ImageFont.load_default()


def _dark_background(image: Image.Image) -> bool:
    rgb = image.convert("RGB")
    width, height = rgb.size
    sample = max(12, min(width, height) // 24)
    boxes = (
        (0, 0, sample, sample),
        (width - sample, 0, width, sample),
        (0, height - sample, sample, height),
        (width - sample, height - sample, width, height),
    )
    means = [sum(ImageStat.Stat(rgb.crop(box)).mean) / 3 for box in boxes]
    return sum(means) / len(means) < 105


def add_key_text(image_path: Path, phrases: Sequence[str], output_path: Path | None = None) -> Path:
    output = output_path or image_path
    image = Image.open(image_path).convert("RGBA")
    width, height = image.size
    cleaned = [clean_key_text(value) for value in phrases]
    cleaned = [value or "本幕重点" for value in cleaned]
    count = max(1, len(cleaned))
    panel_width = width / count
    dark = _dark_background(image)
    text_fill = (255, 218, 103, 255) if dark else (39, 39, 34, 255)
    stroke_fill = (10, 12, 20, 235) if dark else (255, 251, 240, 235)
    accent = (47, 220, 215, 255) if dark else (230, 87, 54, 255)
    draw = ImageDraw.Draw(image)

    for index, phrase in enumerate(cleaned):
        max_size = round(height * 0.058)
        fitted_size = round(panel_width * 0.76 / max(2, len(phrase)))
        font_size = max(24, min(max_size, fitted_size))
        font = _font(font_size)
        box = draw.textbbox((0, 0), phrase, font=font, stroke_width=max(1, font_size // 24))
        text_width = box[2] - box[0]
        text_height = box[3] - box[1]
        center_x = panel_width * (index + 0.5)
        x = round(center_x - text_width / 2)
        y = max(18, round(height * 0.055 - box[1]))
        draw.text(
            (x, y), phrase, font=font, fill=text_fill,
            stroke_width=max(1, font_size // 24), stroke_fill=stroke_fill,
        )
        underline_y = y + text_height + max(8, font_size // 5)
        underline_width = min(text_width, round(panel_width * 0.48))
        draw.rounded_rectangle(
            (
                round(center_x - underline_width / 2), underline_y,
                round(center_x + underline_width / 2), underline_y + max(4, font_size // 10),
            ),
            radius=max(2, font_size // 14), fill=accent,
        )

    image.convert("RGB").save(output, quality=95)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="在分镜图顶部叠加准确的中文重点短语")
    parser.add_argument("image", type=Path)
    parser.add_argument("--text", action="append", required=True, help="按从左到右顺序重复传入")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = add_key_text(args.image, args.text, args.output)
    print(f"OUTPUT={result.resolve()}")


if __name__ == "__main__":
    main()
