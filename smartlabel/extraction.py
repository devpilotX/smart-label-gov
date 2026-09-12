"""Turn OCR text into named, evidence-backed fields.

Every extractor keeps the exact source text that produced a value so the UI and
reports can show the evidence. This module never decides legal status; that is
the job of :mod:`smartlabel.rules`.
"""

import re
from typing import Any

from .models import FieldResult

FLAGS = re.IGNORECASE

# Amounts such as 120, 120.00, 1,200 or 1,200.50
AMOUNT = r"([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,2})?|[0-9]{1,7}(?:\.[0-9]{1,2})?)"
MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
DATE = (
    rf"(\d{{1,2}}[/.-]\d{{1,2}}[/.-]\d{{2,4}}|\d{{1,2}}[/.-]\d{{4}}"
    rf"|\d{{1,2}}\s*{MONTH}\s*[,']?\s*\d{{2,4}}|{MONTH}\s*[,']?\s*\d{{2,4}})"
)
UNITS = r"(ml|mg|mm|cm|kgs?|gms?|grams?|g|ltrs?|litres?|liters?|l|pcs?|pieces?|units?|nos?|n|m)"
UNIT_ALIASES = {
    "kgs": "kg",
    "gm": "g",
    "gms": "g",
    "gram": "g",
    "grams": "g",
    "ltr": "l",
    "ltrs": "l",
    "litre": "l",
    "litres": "l",
    "liter": "l",
    "liters": "l",
    "pc": "piece",
    "pcs": "piece",
    "pieces": "piece",
    "unit": "piece",
    "units": "piece",
    "no": "piece",
    "nos": "piece",
    "n": "piece",
}

# Words that mark the start of the next declaration. Free-text captures such as
# the manufacturer name are cut here so one field never swallows the next.
STOP_WORDS = re.compile(
    r"\b(?:m\.?r\.?p\.?|maximum retail price|net\s*(?:wt|weight|qty|quantity|contents?)|qty|customer|consumer|"
    r"helpline|toll\s*free|packed|pkd|mfg|mfd|manufactured|marketed|imported|made\s+in|country\s+of\s+origin|"
    r"best\s+before|use\s+by|exp|expiry|batch|lot|fssai|e-?mail|phone|tel|www|ingredients|inclusive|incl|"
    r"contact|complaints?)\b",
    FLAGS,
)

MRP_PATTERNS = [
    (re.compile(rf"\b(?:m\.?\s?r\.?\s?p\.?|max(?:imum)?\.?\s+retail\s+price)[^0-9\n]{{0,40}}?{AMOUNT}", FLAGS), 0.0),
    (re.compile(rf"(?:\u20b9|\brs\.?|\binr)\s*{AMOUNT}\s*/-", FLAGS), 0.08),
    (re.compile(rf"\u20b9\s*{AMOUNT}", FLAGS), 0.12),
]
QUANTITY_PATTERNS = [
    (
        re.compile(
            rf"\bnet\s*(?:wt|weight|qty|quantity|contents?|vol|volume)\.?\b[^0-9\n]{{0,15}}([0-9]+(?:\.[0-9]+)?)\s*{UNITS}\b",
            FLAGS,
        ),
        0.0,
    ),
    (
        re.compile(
            rf"\b(?:net|qty|quantity|contents?|weight|volume)\b[^0-9\n]{{0,15}}([0-9]+(?:\.[0-9]+)?)\s*{UNITS}\b",
            FLAGS,
        ),
        0.08,
    ),
]
PHONE_PATTERN = re.compile(
    r"\b(?:customer\s*care|consumer\s*care|consumer\s*complaints?|care\s*line|helpline|toll\s*free|"
    r"contact\s*(?:us|no\.?|number)?|call\s*(?:us)?|phone|tel\.?|ph\.?|mob\.?|whatsapp)\b"
    r"[^0-9+\n]{0,40}(\+?[0-9][0-9 ()./-]{6,}[0-9])",
    FLAGS,
)
EMAIL_PATTERN = re.compile(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
ORIGIN_PATTERN = re.compile(
    r"\b(?:country\s*of\s*origin|made\s*in|product\s*of|produce\s*of|origin)\b\s*[:\-]?\s*([A-Za-z][A-Za-z .]{1,40})",
    FLAGS,
)
MANUFACTURER_PATTERNS = [
    re.compile(
        r"\b(?:manufactured|mfd\.?|mfg\.?|marketed|packed|pkd\.?|imported|distributed)"
        r"(?:\s*(?:and|&|/)\s*(?:manufactured|marketed|packed|imported|distributed))?"
        r"\s*(?:by|for)\b\s*[:\-]?\s*([^\n]{3,120})",
        FLAGS,
    ),
    re.compile(r"\b(?:manufacturer|packer|importer|marketer)\b\s*[:\-]\s*([^\n]{3,120})", FLAGS),
]
DATE_PATTERN = re.compile(
    rf"\b(?:packed\s*on|pkd\.?\s*(?:date|dt\.?|on)?|packing\s*date|date\s*of\s*(?:manufacture|manufacturing|packing|import)|"
    rf"mfg\.?\s*(?:date|dt\.?)?|mfd\.?\s*(?:date|dt\.?|on)?|manufactured\s*(?:on|in)|imported\s*(?:on|in)|"
    rf"month\s*(?:and|&)\s*year\s*of\s*[a-z ]{{3,25}})[^0-9a-z\n]{{0,10}}{DATE}",
    FLAGS,
)
EXPIRY_PATTERN = re.compile(
    rf"\b(?:best\s*before|use\s*by|use\s*before|exp(?:iry)?\.?\s*(?:date|dt\.?)?|expires?\s*(?:on)?)\b[^0-9a-z\n]{{0,10}}"
    rf"(?:{DATE}|(\d{{1,3}}\s*(?:months?|days?|years?|weeks?)(?:\s*from\s*(?:packing|manufacture|mfg\.?|mfd\.?|the\s*date\s*of\s*[a-z]+))?))",
    FLAGS,
)
BATCH_PATTERN = re.compile(r"\b(?:batch|lot)\b\s*(?:no\.?|number|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9/-]{1,20})\b", FLAGS)
FSSAI_PATTERN = re.compile(r"\bfssai\b[^0-9\n]{0,30}([0-9][0-9 ]{10,20}[0-9])", FLAGS)


def normalize_text(text: str) -> str:
    """Collapse whitespace but keep line breaks, which carry layout meaning."""
    text = text.replace("\r", "\n").replace("\u20a8", "Rs")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _to_number(raw: str) -> float:
    return float(raw.replace(",", ""))


def _confidence(value: float) -> float:
    return round(min(0.99, max(0.05, value)), 3)


def _trim(value: str, max_words: int | None = None) -> str:
    match = STOP_WORDS.search(value)
    if match:
        value = value[: match.start()]
    value = value.strip(" .,:;-|/")
    if max_words:
        value = " ".join(value.split()[:max_words])
    return value


def _field(name: str, value: Any, confidence: float, source: str, unit: str | None = None) -> FieldResult:
    return FieldResult(name=name, value=value, confidence=_confidence(confidence), source_text=source.strip(), unit=unit)


def extract_fields(text: str, base_confidence: float = 0.86) -> dict[str, FieldResult]:
    clean = normalize_text(text)
    fields: dict[str, FieldResult] = {}

    for pattern, penalty in MRP_PATTERNS:
        match = pattern.search(clean)
        if match:
            fields["mrp"] = _field("mrp", _to_number(match.group(1)), base_confidence - penalty, match.group(0), "INR")
            break

    for pattern, penalty in QUANTITY_PATTERNS:
        match = pattern.search(clean)
        if match:
            raw_unit = match.group(2).lower()
            unit = UNIT_ALIASES.get(raw_unit, raw_unit)
            fields["net_quantity"] = _field(
                "net_quantity", float(match.group(1)), base_confidence - penalty, match.group(0), unit
            )
            break

    match = PHONE_PATTERN.search(clean)
    if match:
        phone = re.sub(r"\s+", " ", match.group(1)).strip(" .-/")
        fields["customer_care"] = _field("customer_care", phone, base_confidence - 0.08, match.group(0))

    match = EMAIL_PATTERN.search(clean)
    if match:
        fields["customer_care_email"] = _field(
            "customer_care_email", match.group(1).lower(), base_confidence - 0.05, match.group(0)
        )

    match = ORIGIN_PATTERN.search(clean)
    if match:
        origin = _trim(match.group(1), max_words=4)
        first_word = origin.split()[0].lower() if origin else ""
        if origin and first_word not in {"a", "an"} and "facilit" not in origin.lower():
            prefix = match.group(0)[: match.start(1) - match.start(0)]
            fields["country_of_origin"] = _field("country_of_origin", origin.title(), base_confidence - 0.04, prefix + origin)

    for pattern in MANUFACTURER_PATTERNS:
        match = pattern.search(clean)
        if match:
            name = _trim(match.group(1))
            if len(name) >= 3:
                prefix = match.group(0)[: match.start(1) - match.start(0)]
                fields["manufacturer"] = _field("manufacturer", name, base_confidence - 0.12, prefix + name)
                break

    match = DATE_PATTERN.search(clean)
    if match:
        fields["date_marking"] = _field("date_marking", match.group(1), base_confidence - 0.10, match.group(0))

    match = EXPIRY_PATTERN.search(clean)
    if match:
        value = next((group for group in match.groups() if group), None)
        if value:
            fields["expiry"] = _field("expiry", re.sub(r"\s+", " ", value).strip(), base_confidence - 0.10, match.group(0))

    match = BATCH_PATTERN.search(clean)
    if match and any(char.isdigit() for char in match.group(1)):
        fields["batch_number"] = _field("batch_number", match.group(1).upper(), base_confidence - 0.15, match.group(0))

    match = FSSAI_PATTERN.search(clean)
    if match:
        digits = re.sub(r"\D", "", match.group(1))[:14]
        if len(digits) >= 12:
            penalty = 0.05 if len(digits) == 14 else 0.20
            fields["fssai_licence"] = _field("fssai_licence", digits, base_confidence - penalty, match.group(0))

    return fields


def normalize_quantity(value: float, unit: str | None) -> tuple[float, str] | None:
    """Convert a declared quantity to a base unit: kg, l, piece or m."""
    if value <= 0 or not unit:
        return None
    unit = UNIT_ALIASES.get(unit.lower(), unit.lower())
    if unit == "mg":
        return value / 1_000_000, "kg"
    if unit == "g":
        return value / 1_000, "kg"
    if unit == "kg":
        return value, "kg"
    if unit == "ml":
        return value / 1_000, "l"
    if unit == "l":
        return value, "l"
    if unit == "piece":
        return value, "piece"
    if unit == "mm":
        return value / 1_000, "m"
    if unit == "cm":
        return value / 100, "m"
    if unit == "m":
        return value, "m"
    return None
