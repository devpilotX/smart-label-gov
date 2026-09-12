"""Prepared demo labels so the full flow can be shown without a camera or Tesseract."""

from io import BytesIO

DEMO_TEXT = """
SUNRISE FOODS
Premium Basmati Rice
MRP Rs. 120.00 inclusive of all taxes
Net Qty: 500 g
Customer Care: 1800-123-4567
Email: care@sunrisefoods.in
Manufactured by: Sunrise Foods Pvt Ltd, Plot 12, Karnal, Haryana
Packed on: 12/08/2026
Best before: 12 months from packing
Batch No: SF26081
FSSAI Lic. No. 10012031000123
Made in India
""".strip()

DEMO_TEXT_IMPORT = """
OCEAN BLUE
Extra Virgin Olive Oil
Net Quantity: 500 ml
MRP \u20b9 899/- (incl. of all taxes)
Marketed by: Blue Harbour Imports LLP, Mumbai 400001
Best before: 18 months from packing
Batch No: OB-2211
""".strip()

DEMO_SAMPLES: dict[str, dict[str, str]] = {
    "Compliant food label": {
        "text": DEMO_TEXT,
        "product_context": "Food product",
        "sold_by": "Weight",
        "accent": "#1d5fd1",
        "paper": "#f6f1e6",
        "description": "A complete rice pack with every mandatory declaration present. Expect every check to pass.",
    },
    "Imported label with gaps": {
        "text": DEMO_TEXT_IMPORT,
        "product_context": "Imported packaged commodity",
        "sold_by": "Volume",
        "accent": "#0f766e",
        "paper": "#eef6f4",
        "description": "An imported oil bottle missing the country of origin, date marking and customer care. Expect review flags.",
    },
}
DEFAULT_SAMPLE = "Compliant food label"


def _fonts():
    """Best-effort TrueType fonts with a portable fallback."""
    from PIL import ImageFont

    def load(candidates: tuple[str, ...], size: int):
        for name in candidates:
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        try:
            return ImageFont.load_default(size=size)
        except TypeError:  # Pillow < 10.1
            return ImageFont.load_default()

    bold = ("DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf", "LiberationSans-Bold.ttf")
    regular = ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf", "LiberationSans-Regular.ttf")
    return load(bold, 44), load(regular, 30), load(bold, 24)


def demo_image_bytes(sample_name: str | None = None) -> bytes:
    """Render a synthetic label image for the chosen sample."""
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError("Pillow is required for the demo image.") from exc

    sample = DEMO_SAMPLES.get(sample_name or DEFAULT_SAMPLE, DEMO_SAMPLES[DEFAULT_SAMPLE])
    lines = sample["text"].splitlines()
    brand, body_lines = lines[0], lines[1:]
    accent = sample["accent"]

    width = 1200
    height = 215 + 62 * len(body_lines) + 90
    image = Image.new("RGB", (width, height), sample["paper"])
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((55, 45, width - 55, height - 45), radius=28, fill="#fffdf9", outline=accent, width=5)
    draw.rounded_rectangle((55, 45, width - 55, 165), radius=28, fill=accent)
    draw.rectangle((55, 120, width - 55, 165), fill=accent)

    title_font, body_font, small_font = _fonts()
    draw.text((100, 82), brand, fill="white", font=title_font)
    y = 215
    for line in body_lines:
        draw.text((105, y), line, fill="#17283d", font=body_font)
        y += 62

    stamp_top = height - 175
    draw.rounded_rectangle((width - 360, stamp_top, width - 115, stamp_top + 110), radius=18, fill="#e8f7f3", outline="#16957d", width=3)
    draw.text((width - 330, stamp_top + 38), "PACKED", fill="#137764", font=small_font)

    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()
