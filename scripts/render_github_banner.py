from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT_DIR / "assets" / "github-banner.png"


def font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path("C:/Windows/Fonts") / name,
        Path("C:/Windows/Fonts") / name.lower(),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: str, outline: str | None = None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def render_banner(output_path: Path = OUTPUT_PATH) -> None:
    width, height = 1280, 640
    image = Image.new("RGB", (width, height), "#263529")
    draw = ImageDraw.Draw(image)

    for y in range(height):
        t = y / max(height - 1, 1)
        r = int(246 * (1 - t) + 214 * t)
        g = int(239 * (1 - t) + 229 * t)
        b = int(220 * (1 - t) + 190 * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    rounded(draw, (34, 34, width - 34, height - 34), 34, "#fff8eb", "#203225", 4)
    draw.ellipse((820, -150, 1380, 410), fill="#dcebc9")
    draw.ellipse((760, 310, 1130, 760), fill="#f2d7a7")

    title_font = font("georgiab.ttf", 66)
    subtitle_font = font("segoeui.ttf", 24)
    label_font = font("segoeuib.ttf", 22)
    body_font = font("segoeui.ttf", 22)
    small_font = font("segoeui.ttf", 18)

    draw.text((74, 82), "Civitas Library", font=title_font, fill="#1f2d24")
    draw.text((78, 166), "Community-powered mini-library map and book search", font=subtitle_font, fill="#4b5a4f")

    stats = [
        ("Capture", "Shelf list"),
        ("Search", "Nearest first"),
        ("Protect", "Photos stay private"),
    ]
    x = 78
    for label, value in stats:
        rounded(draw, (x, 244, x + 202, 332), 20, "#f5ead5", "#cdbb9f", 2)
        draw.text((x + 22, 262), label, font=small_font, fill="#7a633c")
        draw.text((x + 22, 291), value, font=label_font, fill="#203225")
        x += 224

    map_box = (780, 90, 1168, 398)
    rounded(draw, map_box, 30, "#d7e8ca", "#203225", 4)
    for offset in range(0, 350, 70):
        draw.arc((785 + offset, 120, 1025 + offset, 420), 205, 330, fill="#eef5e5", width=16)
    for pin_x, pin_y, color, csn in [
        (872, 206, "#c9523d", "1"),
        (982, 266, "#416c9f", "12"),
        (1074, 190, "#477c66", "19"),
    ]:
        draw.ellipse((pin_x - 26, pin_y - 26, pin_x + 26, pin_y + 26), fill=color, outline="#203225", width=3)
        draw.text((pin_x - 12, pin_y - 13), csn, font=label_font, fill="#fff8eb")

    rounded(draw, (808, 430, 1154, 560), 26, "#263529", "#203225", 2)
    draw.text((836, 454), "CSN-19", font=label_font, fill="#f2d7a7")
    draw.text((836, 492), "Stable serial IDs for every shelf", font=body_font, fill="#fff8eb")
    draw.text((836, 526), "Generated from the shared database", font=small_font, fill="#d7e8ca")

    book_colors = ["#c9523d", "#e2a236", "#477c66", "#416c9f", "#8c5b92", "#7a633c"]
    for index, color in enumerate(book_colors):
        bx = 88 + index * 38
        by = 456 - index * 9
        rounded(draw, (bx, by, bx + 30, 556), 5, color, "#203225", 2)
    draw.text((338, 480), "Find nearby books with serial-labeled shelves.", font=body_font, fill="#203225")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)


if __name__ == "__main__":
    render_banner()
