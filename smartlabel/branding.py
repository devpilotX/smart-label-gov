"""Brand assets rendered at runtime: raster favicon and inline brand icons.

Run ``python -m smartlabel.branding`` to export ``favicon.ico`` and PNG sizes
into ``assets/`` for hosting platforms that want static icon files.
"""

from pathlib import Path

BRAND_BLUE = "#2167d5"
BRAND_INK = "#17283d"
BRAND_GREEN = "#12b886"

# Official WhatsApp glyph (Simple Icons path data, CC0).
WHATSAPP_ICON_SVG = (
    '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">'
    '<path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164'
    "-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458"
    ".13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612"
    "-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016"
    "-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227"
    " 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347"
    "m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51"
    "-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45"
    "-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142"
    " 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821"
    ' 11.821 0 00-3.48-8.413Z"/></svg>'
)

# Material Symbols "mail" glyph.
MAIL_ICON_SVG = (
    '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">'
    '<path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4-8 5-8-5V6l8 5 '
    '8-5v2z"/></svg>'
)

# Material Symbols "content_copy" glyph.
COPY_ICON_SVG = (
    '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">'
    '<path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1'
    '-.9-2-2-2zm0 16H8V7h11v14z"/></svg>'
)


def _round_line(draw, points, width: int, fill) -> None:
    """Draw a polyline with rounded caps and joints."""
    draw.line(points, fill=fill, width=width, joint="curve")
    radius = width / 2
    for x, y in points:
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def favicon_image(size: int = 128):
    """Render the SmartLabel mark as an RGBA Pillow image at the requested size.

    The design mirrors ``assets/favicon.svg``: a blue gradient tile, a label
    card with two text lines, and a green verification badge.
    """
    from PIL import Image, ImageDraw

    unit = 4  # draw on a 256 px canvas measured in 64 design units
    canvas = 64 * unit

    gradient = Image.new("RGBA", (canvas, canvas))
    gradient_draw = ImageDraw.Draw(gradient)
    start, end = (43, 123, 255), (21, 63, 138)
    for y in range(canvas):
        t = y / (canvas - 1)
        color = tuple(round(start[i] + (end[i] - start[i]) * t) for i in range(3)) + (255,)
        gradient_draw.line([(0, y), (canvas, y)], fill=color)

    mask = Image.new("L", (canvas, canvas), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, canvas - 1, canvas - 1), radius=15 * unit, fill=255)

    image = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    image.paste(gradient, (0, 0), mask)
    draw = ImageDraw.Draw(image)
    white = (255, 255, 255, 255)
    stroke = round(3.2 * unit)

    draw.rounded_rectangle((12 * unit, 12 * unit, 46 * unit, 50 * unit), radius=6 * unit, outline=white, width=stroke)
    _round_line(draw, [(22 * unit, 22 * unit), (42 * unit, 22 * unit)], stroke, white)
    _round_line(draw, [(22 * unit, 29 * unit), (36 * unit, 29 * unit)], stroke, white)
    draw.ellipse((31 * unit, 33 * unit, 53 * unit, 55 * unit), fill=(18, 184, 134, 255), outline=white, width=3 * unit)
    _round_line(draw, [(36.3 * unit, 44 * unit), (40.1 * unit, 47.8 * unit), (47.4 * unit, 40.2 * unit)], stroke, white)

    return image.resize((size, size), Image.Resampling.LANCZOS)


def export_favicons(output_dir: Path) -> list[Path]:
    """Write favicon.ico and common PNG sizes into ``output_dir``."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    ico_path = output_dir / "favicon.ico"
    favicon_image(256).save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    written.append(ico_path)

    for name, size in (("favicon-32.png", 32), ("favicon-192.png", 192), ("apple-touch-icon.png", 180)):
        path = output_dir / name
        favicon_image(size).save(path, format="PNG")
        written.append(path)
    return written


if __name__ == "__main__":
    from .config import ASSETS_DIR

    for written_path in export_favicons(ASSETS_DIR):
        print(written_path)
