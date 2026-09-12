import json
import unittest

from smartlabel.demo import DEMO_SAMPLES, DEMO_TEXT, demo_image_bytes
from smartlabel.models import InspectionResult
from smartlabel.reports import html_bytes, json_bytes, pdf_bytes
from smartlabel.service import screen_images, screen_text


class ServiceTests(unittest.TestCase):
    def test_text_pipeline_returns_reports(self):
        result = screen_text(DEMO_TEXT, "prepared_demo", "Retail packaged commodity", "Weight", 0.96)
        self.assertEqual(result.fields["mrp"].value, 120.0)
        self.assertEqual(result.overall_status, "screened")
        self.assertTrue(result.inspection_id.startswith("SL-"))
        self.assertIn(b"SmartLabel", html_bytes(result))
        self.assertIn(b"inspection_id", json_bytes(result))
        self.assertTrue(pdf_bytes(result).startswith(b"%PDF"))

    def test_result_round_trips_through_json(self):
        result = screen_text(DEMO_TEXT, "prepared_demo", "Food product", "Weight", 0.96)
        restored = InspectionResult.from_dict(json.loads(json_bytes(result)))
        self.assertEqual(restored.inspection_id, result.inspection_id)
        self.assertEqual(restored.overall_status, result.overall_status)
        self.assertEqual(restored.fields["mrp"].value, 120.0)
        self.assertEqual(len(restored.checks), len(result.checks))
        self.assertEqual(restored.raw_text, result.raw_text)

    def test_gap_sample_needs_attention(self):
        sample = DEMO_SAMPLES["Imported label with gaps"]
        result = screen_text(sample["text"], "prepared_demo", sample["product_context"], sample["sold_by"])
        self.assertEqual(result.overall_status, "needs_attention")
        statuses = {check.code: check.status for check in result.checks}
        self.assertEqual(statuses["ORIGIN_PRESENT"], "review")
        self.assertEqual(statuses["CUSTOMER_CARE_PRESENT"], "review")
        self.assertEqual(statuses["UNIT_MATCHES_SOLD_BY"], "pass")
        self.assertEqual(result.fields["mrp"].value, 899.0)

    def test_summary_text_is_shareable(self):
        result = screen_text(DEMO_TEXT, "prepared_demo", "Retail packaged commodity", "Weight")
        summary = result.summary_text()
        self.assertIn(result.inspection_id, summary)
        self.assertIn("Screened", summary)
        self.assertIn("Not a legal certificate", summary)

    def test_image_pipeline_requires_an_image(self):
        with self.assertRaises(ValueError):
            screen_images([], "Retail packaged commodity", "Weight")

    def test_demo_images_render_as_png(self):
        for name in DEMO_SAMPLES:
            self.assertTrue(demo_image_bytes(name).startswith(b"\x89PNG"))


if __name__ == "__main__":
    unittest.main()
