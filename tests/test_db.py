import tempfile
import unittest
from pathlib import Path

from smartlabel.db import Database
from smartlabel.demo import DEMO_TEXT
from smartlabel.models import InspectionResult, utc_now
from smartlabel.service import screen_text


class DatabaseTests(unittest.TestCase):
    def test_save_and_list(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "test.sqlite3")
            result = InspectionResult("SL-TEST", utc_now(), "Retail packaged commodity", "Weight", "PCR_SCREENING_V2", "test")
            db.save(result)
            rows = db.list_recent()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["inspection_id"], "SL-TEST")
            self.assertEqual(rows[0]["sold_by"], "Weight")

    def test_payloads_counts_and_clear(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / "test.sqlite3")
            result = screen_text(DEMO_TEXT, "prepared_demo", "Retail packaged commodity", "Weight")
            db.save(result)
            self.assertEqual(db.count(), 1)
            self.assertEqual(db.status_counts(), {"screened": 1})
            payloads = db.list_payloads()
            self.assertEqual(payloads[0]["inspection_id"], result.inspection_id)
            self.assertEqual(db.get(result.inspection_id)["fields"]["mrp"]["value"], 120.0)
            self.assertEqual(db.clear(), 1)
            self.assertEqual(db.count(), 0)


if __name__ == "__main__":
    unittest.main()
