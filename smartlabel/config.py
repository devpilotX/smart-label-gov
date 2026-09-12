"""Runtime configuration shared by every layer."""

import os
from pathlib import Path

APP_NAME = "SmartLabel Inspector"
APP_TAGLINE = "Evidence-led label screening"
RULE_SET_ID = "PCR_SCREENING_V2"
BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
DEFAULT_DB_PATH = BASE_DIR / "data" / "smartlabel.sqlite3"
DB_PATH = Path(os.getenv("SMARTLABEL_DB_PATH", str(DEFAULT_DB_PATH)))
SUPPORTED_IMAGE_TYPES = ["jpg", "jpeg", "png", "webp"]
PRODUCT_CONTEXTS = [
    "Retail packaged commodity",
    "Imported packaged commodity",
    "Food product",
    "Personal care product",
]
SOLD_BY_OPTIONS = ["Weight", "Volume", "Number", "Length"]


def ensure_data_dir() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
