import tempfile
import unittest
from pathlib import Path

from smartlabel.branding import MAIL_ICON_SVG, WHATSAPP_ICON_SVG, export_favicons, favicon_image


class BrandingTests(unittest.TestCase):
    def test_favicon_renders_at_requested_size(self):
        image = favicon_image(32)
        self.assertEqual(image.size, (32, 32))
        self.assertEqual(image.mode, "RGBA")
        self.assertLess(image.getpixel((0, 0))[3], 40)  # rounded corner stays (almost) transparent
        self.assertEqual(image.getpixel((16, 16))[3], 255)

    def test_export_writes_ico_and_png(self):
        with tempfile.TemporaryDirectory() as folder:
            written = export_favicons(Path(folder))
            names = {path.name for path in written}
            self.assertIn("favicon.ico", names)
            self.assertIn("favicon-32.png", names)
            for path in written:
                self.assertGreater(path.stat().st_size, 0)

    def test_icons_are_inline_svg(self):
        for icon in (WHATSAPP_ICON_SVG, MAIL_ICON_SVG):
            self.assertTrue(icon.startswith("<svg"))
            self.assertTrue(icon.endswith("</svg>"))


if __name__ == "__main__":
    unittest.main()
