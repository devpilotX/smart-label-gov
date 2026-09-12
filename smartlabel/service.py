"""Application workflow: text or images in, a save-ready InspectionResult out."""

from datetime import datetime
from uuid import uuid4

from .config import RULE_SET_ID
from .extraction import extract_fields
from .image import prepare_for_ocr
from .models import InspectionResult, utc_now
from .ocr import read_image
from .rules import evaluate_rules

LOW_CONFIDENCE = 0.55
MIN_WORDS = 8


def new_inspection_id() -> str:
    return f"SL-{datetime.now().strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"


def screen_text(
    text: str,
    source: str,
    product_context: str,
    sold_by: str,
    confidence: float = 0.86,
) -> InspectionResult:
    fields = extract_fields(text, base_confidence=confidence)
    return InspectionResult(
        inspection_id=new_inspection_id(),
        created_at=utc_now(),
        product_context=product_context,
        sold_by=sold_by,
        rule_set=RULE_SET_ID,
        source=source,
        fields=fields,
        checks=evaluate_rules(fields, product_context, sold_by),
        raw_text=text.strip(),
        ocr_confidence=confidence,
    )


def screen_images(image_bytes_list: list[bytes], product_context: str, sold_by: str) -> tuple[InspectionResult, bytes]:
    """Read one or more label images together and screen the combined text."""
    if not image_bytes_list:
        raise ValueError("At least one image is required.")
    prepared_images = [prepare_for_ocr(image_bytes) for image_bytes in image_bytes_list]
    ocr_results = [read_image(image_bytes) for image_bytes in prepared_images]

    combined_text = "\n".join(result.text for result in ocr_results if result.text)
    word_count = sum(result.word_count for result in ocr_results)
    average_confidence = (
        sum(result.average_confidence * result.word_count for result in ocr_results) / word_count if word_count else 0.0
    )

    source = "uploaded_image" if len(image_bytes_list) == 1 else "uploaded_images"
    result = screen_text(combined_text, source, product_context, sold_by, max(LOW_CONFIDENCE, average_confidence))
    result.ocr_confidence = average_confidence
    if word_count < MIN_WORDS:
        result.warnings.append(
            "Very little text was read from the image. Move closer, improve the lighting, and keep the label flat."
        )
    if average_confidence < LOW_CONFIDENCE:
        result.warnings.append(
            "OCR confidence is low. Check the images and confirm each field before relying on the result."
        )
    return result, prepared_images[0]


def screen_image(image_bytes: bytes, product_context: str, sold_by: str) -> tuple[InspectionResult, bytes]:
    return screen_images([image_bytes], product_context, sold_by)
