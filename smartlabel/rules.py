"""Deterministic, testable screening checks.

Each rule receives the extracted fields and returns a ``CheckResult`` whose
status is ``pass``, ``review``, ``fail`` or ``not_applicable`` together with a
message a reviewer can read without knowing the code.
"""

from .extraction import normalize_quantity
from .models import CheckResult, FieldResult

SOLD_BY_UNITS = {"Weight": "kg", "Volume": "l", "Number": "piece", "Length": "m"}

RULE_DEFINITIONS: list[dict[str, str]] = [
    {"code": "MRP_PRESENT", "title": "Maximum retail price", "check": "MRP is present and greater than zero", "applies": "All products"},
    {"code": "NET_QUANTITY_PRESENT", "title": "Net quantity", "check": "Net quantity is present with a recognised unit", "applies": "All products"},
    {"code": "UNIT_MATCHES_SOLD_BY", "title": "Quantity unit", "check": "Declared unit matches how the product is sold", "applies": "When net quantity is found"},
    {"code": "UNIT_PRICE_CALCULABLE", "title": "Unit sale price", "check": "Unit sale price can be calculated from MRP and quantity", "applies": "When MRP and quantity are found"},
    {"code": "MANUFACTURER_PRESENT", "title": "Manufacturer or packer", "check": "Name of the manufacturer, packer, or importer is visible", "applies": "All products"},
    {"code": "DATE_MARKING_PRESENT", "title": "Date marking", "check": "Month and year of manufacture, packing, or import is visible", "applies": "All products"},
    {"code": "CUSTOMER_CARE_PRESENT", "title": "Customer care contact", "check": "A consumer care phone number or email is visible", "applies": "All products"},
    {"code": "ORIGIN_PRESENT", "title": "Country of origin", "check": "Country of origin is visible", "applies": "Imported products"},
    {"code": "FSSAI_PRESENT", "title": "FSSAI licence", "check": "A 14-digit FSSAI licence number is visible", "applies": "Food products"},
]


def _missing(fields: dict[str, FieldResult], key: str) -> bool:
    return key not in fields or fields[key].value in (None, "")


def _check(code: str, status: str, message: str, evidence: list[str], value=None) -> CheckResult:
    title = next(rule["title"] for rule in RULE_DEFINITIONS if rule["code"] == code)
    return CheckResult(code, title, status, message, evidence, value)


def evaluate_rules(
    fields: dict[str, FieldResult],
    product_context: str = "Retail packaged commodity",
    sold_by: str = "Weight",
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    context = product_context.lower()
    is_import = "import" in context
    is_food = "food" in context

    # MRP
    if _missing(fields, "mrp"):
        checks.append(_check("MRP_PRESENT", "review", "MRP was not found with enough confidence.", ["mrp"]))
    else:
        mrp = float(fields["mrp"].value)
        if mrp > 0:
            checks.append(_check("MRP_PRESENT", "pass", f"MRP \u20b9{mrp:,.2f} was found and is greater than zero.", ["mrp"], mrp))
        else:
            checks.append(_check("MRP_PRESENT", "fail", "MRP must be greater than zero.", ["mrp"], mrp))

    # Net quantity
    quantity_field = None if _missing(fields, "net_quantity") else fields["net_quantity"]
    normalized = None
    if quantity_field is None:
        checks.append(_check("NET_QUANTITY_PRESENT", "review", "Net quantity was not found with enough confidence.", ["net_quantity"]))
    else:
        quantity = float(quantity_field.value)
        if quantity > 0:
            normalized = normalize_quantity(quantity, quantity_field.unit)
            unit_text = f" {quantity_field.unit}" if quantity_field.unit else ""
            checks.append(_check("NET_QUANTITY_PRESENT", "pass", f"Net quantity {quantity:g}{unit_text} was found.", ["net_quantity"], quantity))
        else:
            checks.append(_check("NET_QUANTITY_PRESENT", "fail", "Net quantity must be greater than zero.", ["net_quantity"], quantity))

    # Unit consistency with the sold-by selection
    expected_unit = SOLD_BY_UNITS.get(sold_by)
    if normalized is None or expected_unit is None:
        checks.append(_check("UNIT_MATCHES_SOLD_BY", "not_applicable", "Checked once a net quantity with a recognised unit is available.", ["net_quantity"]))
    elif normalized[1] == expected_unit:
        checks.append(_check("UNIT_MATCHES_SOLD_BY", "pass", f"Unit '{quantity_field.unit}' is consistent with a product sold by {sold_by.lower()}.", ["net_quantity"], normalized[1]))
    else:
        checks.append(
            _check(
                "UNIT_MATCHES_SOLD_BY",
                "review",
                f"Unit '{quantity_field.unit}' does not match a product sold by {sold_by.lower()}. Confirm the declaration or the selected sold-by option.",
                ["net_quantity"],
                normalized[1],
            )
        )

    # Unit sale price
    if "mrp" in fields and quantity_field is not None:
        if normalized and float(fields["mrp"].value) > 0:
            base_quantity, base_unit = normalized
            unit_price = round(float(fields["mrp"].value) / base_quantity, 2)
            checks.append(
                _check("UNIT_PRICE_CALCULABLE", "pass", f"Calculated at \u20b9{unit_price:,.2f} per {base_unit}.", ["mrp", "net_quantity"], {"value": unit_price, "unit": base_unit})
            )
        else:
            checks.append(_check("UNIT_PRICE_CALCULABLE", "review", "Unit sale price needs a manual calculation check.", ["mrp", "net_quantity"]))
    else:
        checks.append(_check("UNIT_PRICE_CALCULABLE", "not_applicable", "Not calculated until price and quantity are available.", ["mrp", "net_quantity"]))

    # Manufacturer, packer or importer
    if _missing(fields, "manufacturer"):
        checks.append(_check("MANUFACTURER_PRESENT", "review", "Name and address of the manufacturer, packer, or importer was not found.", ["manufacturer"]))
    else:
        checks.append(_check("MANUFACTURER_PRESENT", "pass", "Manufacturer, packer, or importer declaration was found.", ["manufacturer"], fields["manufacturer"].value))

    # Date marking
    if _missing(fields, "date_marking"):
        checks.append(_check("DATE_MARKING_PRESENT", "review", "Month and year of manufacture, packing, or import was not found.", ["date_marking"]))
    else:
        checks.append(_check("DATE_MARKING_PRESENT", "pass", f"Date marking '{fields['date_marking'].value}' was found.", ["date_marking"], fields["date_marking"].value))

    # Customer care
    has_phone = not _missing(fields, "customer_care")
    has_email = not _missing(fields, "customer_care_email")
    if not has_phone and not has_email:
        checks.append(_check("CUSTOMER_CARE_PRESENT", "review", "Customer care phone number or email was not found.", ["customer_care", "customer_care_email"]))
    else:
        found = []
        if has_phone:
            found.append(f"phone {fields['customer_care'].value}")
        if has_email:
            found.append(f"email {fields['customer_care_email'].value}")
        value = fields["customer_care"].value if has_phone else fields["customer_care_email"].value
        checks.append(_check("CUSTOMER_CARE_PRESENT", "pass", "Customer care contact was found: " + " and ".join(found) + ".", ["customer_care", "customer_care_email"], value))

    # Country of origin
    has_origin = not _missing(fields, "country_of_origin")
    if is_import and not has_origin:
        checks.append(_check("ORIGIN_PRESENT", "review", "Country of origin is required for an imported product and was not found.", ["country_of_origin"]))
    elif has_origin:
        suffix = "" if is_import else " (optional for this context)"
        checks.append(_check("ORIGIN_PRESENT", "pass", f"Country of origin '{fields['country_of_origin'].value}' was found{suffix}.", ["country_of_origin"], fields["country_of_origin"].value))
    else:
        checks.append(_check("ORIGIN_PRESENT", "not_applicable", "Only required for imported products.", ["country_of_origin"]))

    # FSSAI licence for food products
    has_fssai = not _missing(fields, "fssai_licence")
    if is_food and not has_fssai:
        checks.append(_check("FSSAI_PRESENT", "review", "FSSAI licence number was not found. Food products normally display a 14-digit licence number.", ["fssai_licence"]))
    elif is_food:
        checks.append(_check("FSSAI_PRESENT", "pass", f"FSSAI licence {fields['fssai_licence'].value} was found.", ["fssai_licence"], fields["fssai_licence"].value))
    else:
        checks.append(_check("FSSAI_PRESENT", "not_applicable", "Only checked for food products.", ["fssai_licence"]))

    return checks
