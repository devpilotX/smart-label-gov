import unittest

from smartlabel.demo import DEMO_TEXT
from smartlabel.extraction import extract_fields, normalize_quantity


class ExtractionTests(unittest.TestCase):
    def test_extracts_common_label_fields(self):
        text = "MRP Rs. 120 inclusive of all taxes Net Qty: 500 g Customer Care: 1800-123-4567 Made in India"
        fields = extract_fields(text)
        self.assertEqual(fields["mrp"].value, 120.0)
        self.assertEqual(fields["net_quantity"].unit, "g")
        self.assertEqual(fields["customer_care"].value, "1800-123-4567")
        self.assertEqual(fields["country_of_origin"].value, "India")

    def test_extracts_full_demo_label(self):
        fields = extract_fields(DEMO_TEXT)
        self.assertEqual(fields["mrp"].value, 120.0)
        self.assertEqual((fields["net_quantity"].value, fields["net_quantity"].unit), (500.0, "g"))
        self.assertEqual(fields["customer_care"].value, "1800-123-4567")
        self.assertEqual(fields["customer_care_email"].value, "care@sunrisefoods.in")
        self.assertTrue(fields["manufacturer"].value.startswith("Sunrise Foods Pvt Ltd"))
        self.assertEqual(fields["date_marking"].value, "12/08/2026")
        self.assertEqual(fields["expiry"].value, "12 months from packing")
        self.assertEqual(fields["batch_number"].value, "SF26081")
        self.assertEqual(fields["fssai_licence"].value, "10012031000123")
        self.assertEqual(fields["country_of_origin"].value, "India")

    def test_handles_rupee_symbol_and_thousands_separator(self):
        fields = extract_fields("M.R.P. \u20b9 1,250.00 (incl. of all taxes)\nNet Wt. 1 kg")
        self.assertEqual(fields["mrp"].value, 1250.0)
        self.assertEqual((fields["net_quantity"].value, fields["net_quantity"].unit), (1.0, "kg"))

    def test_unit_aliases_are_normalized(self):
        self.assertEqual(extract_fields("Net Quantity 200 ML")["net_quantity"].unit, "ml")
        self.assertEqual(extract_fields("Net Qty: 12 Nos")["net_quantity"].unit, "piece")
        self.assertEqual(extract_fields("Net Wt 250 gms")["net_quantity"].unit, "g")

    def test_manufacturer_is_trimmed_at_next_declaration(self):
        text = "Manufactured by: Sunrise Foods Pvt Ltd Packed on: 12/08/2026 Made in India"
        fields = extract_fields(text)
        self.assertEqual(fields["manufacturer"].value, "Sunrise Foods Pvt Ltd")
        self.assertEqual(fields["date_marking"].value, "12/08/2026")
        self.assertEqual(fields["country_of_origin"].value, "India")

    def test_keeps_evidence_text(self):
        fields = extract_fields("MRP Rs. 99/-")
        self.assertIn("MRP", fields["mrp"].source_text)
        self.assertLessEqual(fields["mrp"].confidence, 0.99)

    def test_unrelated_text_yields_no_fields(self):
        self.assertEqual(extract_fields("Lorem ipsum dolor sit amet"), {})

    def test_normalizes_weight(self):
        self.assertEqual(normalize_quantity(500, "g"), (0.5, "kg"))

    def test_normalizes_volume_and_count(self):
        self.assertEqual(normalize_quantity(250, "ml"), (0.25, "l"))
        self.assertEqual(normalize_quantity(12, "piece"), (12, "piece"))
        self.assertIsNone(normalize_quantity(0, "g"))


if __name__ == "__main__":
    unittest.main()
