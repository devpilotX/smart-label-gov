"""Image preparation for OCR. Pure Pillow so it runs anywhere."""

from io import BytesIO


def prepare_for_ocr(image_bytes: bytes, max_side: int = 2000, min_side: int = 1100) -> bytes:
    """Normalize an uploaded image for OCR while keeping the original bytes untouched.

    Steps: honour EXIF rotation, bring the longest side into a range Tesseract
    reads well, convert to grayscale, stretch contrast and sharpen slightly.
    """
    try:
        from PIL import Image, ImageEnhance, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow is required for image processing.") from exc

    with Image.open(BytesIO(image_bytes)) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")

    longest = max(image.size)
    if longest > max_side:
        image.thumbnail((max_side, max_side))
    elif longest < min_side:
        factor = min_side / longest
        image = image.resize((round(image.width * factor), round(image.height * factor)), Image.Resampling.LANCZOS)

    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = ImageEnhance.Sharpness(gray).enhance(1.4)
    output = BytesIO()
    gray.save(output, format="PNG", optimize=True)
    return output.getvalue()


def image_metadata(image_bytes: bytes) -> dict[str, int | str]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required for image metadata.") from exc

    with Image.open(BytesIO(image_bytes)) as image:
        return {"format": image.format or "unknown", "width": image.width, "height": image.height}
