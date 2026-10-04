"""Generate the Blipkit app icon for PNG, ICO, and macOS ICNS."""

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ICONSET = ASSETS / "Blipkit.iconset"
SIZE = 1024
SUPERSAMPLE = 4


def _point(x: float, y: float) -> tuple[int, int]:
    return round(x * SUPERSAMPLE), round(y * SUPERSAMPLE)


def _cubic(
    start: tuple[float, float],
    control_1: tuple[float, float],
    control_2: tuple[float, float],
    end: tuple[float, float],
    steps: int = 16,
) -> list[tuple[int, int]]:
    points = []
    for index in range(1, steps + 1):
        t = index / steps
        inverse = 1 - t
        x = (
            inverse**3 * start[0]
            + 3 * inverse**2 * t * control_1[0]
            + 3 * inverse * t**2 * control_2[0]
            + t**3 * end[0]
        )
        y = (
            inverse**3 * start[1]
            + 3 * inverse**2 * t * control_1[1]
            + 3 * inverse * t**2 * control_2[1]
            + t**3 * end[1]
        )
        points.append(_point(x, y))
    return points


def _mark_points() -> list[tuple[int, int]]:
    points = [_point(164, 378), _point(392, 445)]
    points += _cubic((392, 445), (420, 454), (431, 449), (446, 423))
    points.append(_point(509, 291))
    points += _cubic((509, 291), (524, 259), (540, 263), (543, 300))
    points.append(_point(556, 403))
    points += _cubic((556, 403), (562, 448), (581, 458), (615, 439))
    points += [_point(855, 324), _point(652, 485)]
    points += _cubic((652, 485), (625, 506), (632, 520), (663, 524))
    points += [_point(847, 550), _point(651, 580)]
    points += _cubic((651, 580), (620, 585), (617, 602), (638, 625))
    points.append(_point(758, 756))
    points.append(_point(565, 647))
    points += _cubic((565, 647), (538, 631), (526, 642), (519, 672))
    points.append(_point(477, 812))
    points += _cubic((477, 812), (468, 842), (453, 833), (447, 802))
    points.append(_point(420, 662))
    points += _cubic((420, 662), (414, 629), (395, 624), (367, 639))
    points += [_point(207, 725), _point(350, 575)]
    points += _cubic((350, 575), (369, 556), (361, 543), (333, 526))
    return points


def _gradient(
    size: int,
    top: tuple[int, int, int, int],
    bottom: tuple[int, int, int, int],
) -> Image.Image:
    image = Image.new("RGBA", (size, size))
    draw = ImageDraw.Draw(image)
    for y in range(size):
        ratio = y / max(1, size - 1)
        color = tuple(round(a + (b - a) * ratio) for a, b in zip(top, bottom, strict=True))
        draw.line((0, y, size, y), fill=color)
    return image


def draw_icon(size: int = SIZE) -> Image.Image:
    render_size = SIZE * SUPERSAMPLE
    image = Image.new("RGBA", (render_size, render_size), (0, 0, 0, 0))

    tile_box = (*_point(62, 62), *_point(962, 962))
    tile_mask = Image.new("L", (render_size, render_size), 0)
    ImageDraw.Draw(tile_mask).rounded_rectangle(
        tile_box,
        radius=224 * SUPERSAMPLE,
        fill=255,
    )

    shadow = tile_mask.filter(ImageFilter.GaussianBlur(25 * SUPERSAMPLE))
    shadow_layer = Image.new("RGBA", (render_size, render_size), (0, 0, 0, 118))
    shadow_layer.putalpha(shadow.point(lambda value: round(value * 0.48)))
    image.alpha_composite(shadow_layer)

    tile = _gradient(
        render_size,
        (26, 28, 34, 255),
        (8, 9, 12, 255),
    )
    tile.putalpha(tile_mask)
    image.alpha_composite(tile)

    frame = ImageDraw.Draw(image)
    frame.rounded_rectangle(
        tile_box,
        radius=224 * SUPERSAMPLE,
        outline=(56, 60, 70, 210),
        width=6 * SUPERSAMPLE,
    )

    mark_mask = Image.new("L", (render_size, render_size), 0)
    ImageDraw.Draw(mark_mask).polygon(_mark_points(), fill=255)

    waveform = [
        _point(178, 535),
        _point(302, 535),
        _point(352, 505),
        _point(405, 566),
        _point(456, 431),
        _point(515, 643),
        _point(568, 460),
        _point(624, 570),
        _point(683, 519),
        _point(846, 519),
    ]
    channel_mask = Image.new("L", (render_size, render_size), 0)
    ImageDraw.Draw(channel_mask).line(
        waveform,
        fill=255,
        width=48 * SUPERSAMPLE,
        joint="curve",
    )
    visible_channel = ImageChops.multiply(channel_mask, mark_mask)
    split_mark_mask = ImageChops.subtract(mark_mask, visible_channel)

    mark = _gradient(
        render_size,
        (248, 249, 251, 255),
        (190, 198, 210, 255),
    )
    mark.putalpha(split_mark_mask)
    image.alpha_composite(mark)

    pulse_mask = Image.new("L", (render_size, render_size), 0)
    ImageDraw.Draw(pulse_mask).line(
        waveform,
        fill=255,
        width=14 * SUPERSAMPLE,
        joint="curve",
    )
    pulse_mask = ImageChops.multiply(pulse_mask, mark_mask)
    pulse = Image.new("RGBA", (render_size, render_size), (45, 119, 255, 255))
    pulse.putalpha(pulse_mask)
    image.alpha_composite(pulse)

    return image.resize((size, size), Image.Resampling.LANCZOS)


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
        icon.resize((points, points), Image.Resampling.LANCZOS).save(
            ICONSET / f"icon_{points}x{points}.png"
        )
        icon.resize((points * 2, points * 2), Image.Resampling.LANCZOS).save(
            ICONSET / f"icon_{points}x{points}@2x.png"
        )

    iconutil = shutil.which("iconutil")
    if iconutil:
        if subprocess.run(
            [iconutil, "-c", "icns", str(ICONSET), "-o", str(ASSETS / "icon.icns")],
            check=False,
        ).returncode:
            raise RuntimeError("iconutil failed to generate assets/icon.icns")
    else:
        icon.save(ASSETS / "icon.icns", format="ICNS")


if __name__ == "__main__":
    main()
