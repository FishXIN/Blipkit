"""Generate Blipkit PNG, ICO, and macOS iconset sources."""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ICONSET = ASSETS / "Blipkit.iconset"
SIZE = 1024


def draw_icon(size: int) -> Image.Image:
    scale = size / SIZE
    image = Image.new("RGBA", (size, size), (245, 246, 247, 255))
    draw = ImageDraw.Draw(image)

    margin = int(110 * scale)
    radius = int(184 * scale)
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=radius,
        fill=(255, 255, 255, 255),
        outline=(229, 230, 235, 255),
        width=max(1, int(14 * scale)),
    )

    bars = (130, 250, 390, 560, 390, 250, 130)
    bar_width = int(66 * scale)
    gap = int(42 * scale)
    total = len(bars) * bar_width + (len(bars) - 1) * gap
    start_x = (size - total) // 2
    center_y = size // 2
    for index, height in enumerate(bars):
        x1 = start_x + index * (bar_width + gap)
        y1 = center_y - int(height * scale) // 2
        x2 = x1 + bar_width
        y2 = center_y + int(height * scale) // 2
        draw.rounded_rectangle(
            (x1, y1, x2, y2),
            radius=bar_width // 2,
            fill=(91, 141, 239, 255),
        )
    return image


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon = draw_icon(SIZE)
    icon.save(ASSETS / "icon.png")
    icon.save(
        ASSETS / "icon.ico",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    ICONSET.mkdir(exist_ok=True)
    for points in (16, 32, 128, 256, 512):
        draw_icon(points).save(ICONSET / f"icon_{points}x{points}.png")
        draw_icon(points * 2).save(ICONSET / f"icon_{points}x{points}@2x.png")


if __name__ == "__main__":
    main()
