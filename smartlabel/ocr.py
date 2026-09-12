"""Tesseract adapter. This is the only module that knows how OCR is invoked."""

import shutil
from dataclasses import dataclass
from io import BytesIO


@dataclass
class OcrWord:
    text: str
    confidence: float
    bbox: tuple[int, int, int, int] | None = None


@dataclass
class OcrResult:
    text: str
    average_confidence: float
    words: list[OcrWord]

    @property
    def word_count(self) -> int:
        return len(self.words)


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def tesseract_version() -> str | None:
    try:
        import pytesseract

        return str(pytesseract.get_tesseract_version())
    except Exception:  # noqa: BLE001 - version lookup is informational only
        return None


def _run(image, language: str, config: str) -> OcrResult:
    import pytesseract

    data = pytesseract.image_to_data(image, lang=language, output_type=pytesseract.Output.DICT, config=config)
    texts = data.get("text", [])
    count = len(texts)

    def column(name: str) -> list:
        values = data.get(name)
        return list(values) if values is not None and len(values) == count else [0] * count

    confs = column("conf")
    lefts, tops, widths, heights = column("left"), column("top"), column("width"), column("height")
    blocks, paragraphs, line_numbers = column("block_num"), column("par_num"), column("line_num")

    words: list[OcrWord] = []
    lines: dict[tuple[int, int, int], list[str]] = {}
    for index in range(count):
        text = str(texts[index]).strip()
        if not text:
            continue
        try:
            confidence = float(confs[index]) / 100.0
        except (TypeError, ValueError):
            confidence = 0.0
        if confidence < 0:
            continue
        confidence = min(1.0, confidence)
        bbox = (int(lefts[index]), int(tops[index]), int(widths[index]), int(heights[index]))
        words.append(OcrWord(text=text, confidence=confidence, bbox=bbox))
        key = (int(blocks[index]), int(paragraphs[index]), int(line_numbers[index]))
        lines.setdefault(key, []).append(text)

    average = sum(word.confidence for word in words) / len(words) if words else 0.0
    text = "\n".join(" ".join(parts) for parts in lines.values())
    return OcrResult(text=text, average_confidence=average, words=words)


def read_image(image_bytes: bytes, language: str = "eng") -> OcrResult:
    """Read text, line structure and word confidences from an image with local Tesseract.

    A first pass assumes a uniform block of text (PSM 6). When it reads very
    little, a second pass with column-aware segmentation (PSM 4) is tried and
    the better result is kept.
    """
    try:
        import pytesseract  # noqa: F401
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Install pytesseract and Pillow to enable OCR.") from exc

    if not tesseract_available():
        raise RuntimeError("Tesseract is not installed or is not on PATH.")

    image = Image.open(BytesIO(image_bytes))
    best = _run(image, language, "--psm 6")
    if best.word_count < 6 or best.average_confidence < 0.45:
        alternative = _run(image, language, "--psm 4")
        best_score = best.word_count * (best.average_confidence + 0.01)
        alternative_score = alternative.word_count * (alternative.average_confidence + 0.01)
        if alternative_score > best_score:
            best = alternative
    return best
