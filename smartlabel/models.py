"""Shared data models used by extraction, rules, persistence, reports and UI."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

STATUS_ORDER = ("screened", "needs_attention", "potential_issue")
STATUS_LABELS = {
    "screened": "Screened",
    "needs_attention": "Needs attention",
    "potential_issue": "Potential issue",
}
CHECK_STATUS_LABELS = {
    "pass": "Pass",
    "review": "Review",
    "fail": "Fail",
    "not_applicable": "Not applicable",
}
FIELD_LABELS = {
    "mrp": "MRP",
    "net_quantity": "Net quantity",
    "customer_care": "Customer care phone",
    "customer_care_email": "Customer care email",
    "manufacturer": "Manufacturer / packer",
    "date_marking": "Date marking",
    "expiry": "Best before / expiry",
    "batch_number": "Batch or lot",
    "country_of_origin": "Country of origin",
    "fssai_licence": "FSSAI licence",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class FieldResult:
    name: str
    value: Any = None
    confidence: float = 0.0
    source_text: str = ""
    unit: str | None = None
    bbox: tuple[int, int, int, int] | None = None

    @property
    def display_value(self) -> str:
        if self.value is None or self.value == "":
            return ""
        if self.name == "mrp":
            try:
                return f"\u20b9{float(self.value):,.2f}"
            except (TypeError, ValueError):
                return str(self.value)
        text = f"{self.value:g}" if isinstance(self.value, float) else str(self.value)
        return f"{text} {self.unit}" if self.unit else text

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FieldResult":
        bbox = data.get("bbox")
        return cls(
            name=str(data.get("name", "")),
            value=data.get("value"),
            confidence=float(data.get("confidence", 0.0) or 0.0),
            source_text=str(data.get("source_text", "")),
            unit=data.get("unit"),
            bbox=tuple(bbox) if isinstance(bbox, (list, tuple)) and len(bbox) == 4 else None,
        )


@dataclass
class CheckResult:
    code: str
    title: str
    status: str
    message: str
    evidence_fields: list[str] = field(default_factory=list)
    value: Any = None

    @property
    def status_label(self) -> str:
        return CHECK_STATUS_LABELS.get(self.status, self.status.replace("_", " ").title())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckResult":
        return cls(
            code=str(data.get("code", "")),
            title=str(data.get("title", "")),
            status=str(data.get("status", "review")),
            message=str(data.get("message", "")),
            evidence_fields=list(data.get("evidence_fields") or []),
            value=data.get("value"),
        )


@dataclass
class InspectionResult:
    inspection_id: str
    created_at: str
    product_context: str
    sold_by: str
    rule_set: str
    source: str
    fields: dict[str, FieldResult] = field(default_factory=dict)
    checks: list[CheckResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw_text: str = ""
    ocr_confidence: float = 0.0

    @property
    def review_count(self) -> int:
        return sum(check.status in {"review", "fail"} for check in self.checks)

    @property
    def pass_count(self) -> int:
        return sum(check.status == "pass" for check in self.checks)

    @property
    def fail_count(self) -> int:
        return sum(check.status == "fail" for check in self.checks)

    @property
    def applicable_count(self) -> int:
        return sum(check.status != "not_applicable" for check in self.checks)

    @property
    def overall_status(self) -> str:
        if any(check.status == "fail" for check in self.checks):
            return "potential_issue"
        if any(check.status == "review" for check in self.checks):
            return "needs_attention"
        return "screened"

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.overall_status, self.overall_status.replace("_", " ").title())

    @property
    def unit_price(self) -> dict[str, Any] | None:
        for check in self.checks:
            if check.code == "UNIT_PRICE_CALCULABLE" and isinstance(check.value, dict):
                return check.value
        return None

    def summary_text(self) -> str:
        """Plain-text summary used for sharing by WhatsApp, email or clipboard."""
        lines = [
            f"SmartLabel Inspector report {self.inspection_id}",
            f"Status: {self.status_label} ({self.pass_count} pass, {self.review_count} need attention)",
            f"Context: {self.product_context}, sold by {self.sold_by.lower()}",
        ]
        for key in ("mrp", "net_quantity", "manufacturer", "customer_care", "date_marking", "country_of_origin"):
            if key in self.fields and self.fields[key].display_value:
                lines.append(f"{FIELD_LABELS.get(key, key)}: {self.fields[key].display_value}")
        unit_price = self.unit_price
        if unit_price:
            lines.append(f"Unit price: \u20b9{unit_price['value']:,.2f} per {unit_price['unit']}")
        attention = [check.title for check in self.checks if check.status in {"review", "fail"}]
        if attention:
            lines.append("Needs attention: " + ", ".join(attention))
        lines.append("Screening aid only. Not a legal certificate.")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "inspection_id": self.inspection_id,
            "created_at": self.created_at,
            "product_context": self.product_context,
            "sold_by": self.sold_by,
            "rule_set": self.rule_set,
            "source": self.source,
            "overall_status": self.overall_status,
            "summary": {
                "pass": self.pass_count,
                "review": self.review_count,
                "fail": self.fail_count,
                "applicable": self.applicable_count,
            },
            "ocr_confidence": round(self.ocr_confidence, 4),
            "fields": {name: result.to_dict() for name, result in self.fields.items()},
            "checks": [check.to_dict() for check in self.checks],
            "warnings": self.warnings,
            "raw_text": self.raw_text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InspectionResult":
        fields = {
            str(name): FieldResult.from_dict({"name": name, **payload})
            for name, payload in (data.get("fields") or {}).items()
            if isinstance(payload, dict)
        }
        checks = [CheckResult.from_dict(item) for item in (data.get("checks") or []) if isinstance(item, dict)]
        return cls(
            inspection_id=str(data.get("inspection_id", "")),
            created_at=str(data.get("created_at", "")),
            product_context=str(data.get("product_context", "")),
            sold_by=str(data.get("sold_by", "")),
            rule_set=str(data.get("rule_set", "")),
            source=str(data.get("source", "")),
            fields=fields,
            checks=checks,
            warnings=list(data.get("warnings") or []),
            raw_text=str(data.get("raw_text", "") or ""),
            ocr_confidence=float(data.get("ocr_confidence", 0.0) or 0.0),
        )
