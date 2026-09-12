import unittest

from smartlabel.demo import DEMO_TEXT
from smartlabel.extraction import extract_fields
from smartlabel.rules import RULE_DEFINITIONS, evaluate_rules


def _by_code(checks):
    return {check.code: check for check in checks}


class RuleTests(unittest.TestCase):
    def test_complete_label_has_passes(self):
        fields = extract_fields("MRP Rs. 120 Net Qty: 500 g Customer Care: 1800-123-4567")
        codes = _by_code(evaluate_rules(fields))
        self.assertEqual(codes["MRP_PRESENT"].status, "pass")
        self.assertEqual(codes["NET_QUANTITY_PRESENT"].status, "pass")
        self.assertEqual(codes["UNIT_PRICE_CALCULABLE"].status, "pass")
        self.assertEqual(codes["UNIT_PRICE_CALCULABLE"].value, {"value": 240.0, "unit": "kg"})

    def test_missing_mrp_needs_attention(self):
        checks = evaluate_rules(extract_fields("Net Qty: 500 g"))
        self.assertEqual(_by_code(checks)["MRP_PRESENT"].status, "review")

    def test_every_defined_rule_is_evaluated_once(self):
        checks = evaluate_rules(extract_fields(DEMO_TEXT), "Food product", "Weight")
        self.assertEqual([check.code for check in checks], [rule["code"] for rule in RULE_DEFINITIONS])

    def test_demo_label_passes_everything(self):
        checks = evaluate_rules(extract_fields(DEMO_TEXT), "Food product", "Weight")
        self.assertEqual([check.code for check in checks if check.status in {"review", "fail"}], [])

    def test_import_requires_origin(self):
        fields = extract_fields("MRP Rs. 120 Net Qty: 500 g")
        self.assertEqual(_by_code(evaluate_rules(fields, "Imported packaged commodity", "Weight"))["ORIGIN_PRESENT"].status, "review")
        self.assertEqual(_by_code(evaluate_rules(fields, "Retail packaged commodity", "Weight"))["ORIGIN_PRESENT"].status, "not_applicable")

    def test_unit_mismatch_is_flagged(self):
        fields = extract_fields("Net Qty: 500 ml")
        self.assertEqual(_by_code(evaluate_rules(fields, "Retail packaged commodity", "Weight"))["UNIT_MATCHES_SOLD_BY"].status, "review")
        self.assertEqual(_by_code(evaluate_rules(fields, "Retail packaged commodity", "Volume"))["UNIT_MATCHES_SOLD_BY"].status, "pass")

    def test_food_products_expect_fssai(self):
        fields = extract_fields("MRP Rs. 50 Net Qty: 100 g")
        self.assertEqual(_by_code(evaluate_rules(fields, "Food product", "Weight"))["FSSAI_PRESENT"].status, "review")
        self.assertEqual(_by_code(evaluate_rules(fields, "Retail packaged commodity", "Weight"))["FSSAI_PRESENT"].status, "not_applicable")

    def test_zero_mrp_is_a_failure(self):
        checks = evaluate_rules(extract_fields("MRP Rs. 0 Net Qty: 100 g"))
        self.assertEqual(_by_code(checks)["MRP_PRESENT"].status, "fail")


if __name__ == "__main__":
    unittest.main()
