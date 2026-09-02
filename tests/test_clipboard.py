import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotspot_share.clipboard import (
    set_system_clipboard_text, set_system_clipboard_image,
    get_system_clipboard, ALLOWED_IMAGE_MIMES
)

class TestClipboard(unittest.TestCase):
    def test_empty_inputs(self):
        self.assertFalse(set_system_clipboard_text(""))
        self.assertFalse(set_system_clipboard_image(b""))

    def test_allowed_mimes(self):
        self.assertIn("image/png", ALLOWED_IMAGE_MIMES)
        self.assertIn("image/jpeg", ALLOWED_IMAGE_MIMES)
        self.assertIn("image/webp", ALLOWED_IMAGE_MIMES)

    @patch("shutil.which", return_value=None)
    def test_get_clipboard_fallback(self, mock_which):
        res = get_system_clipboard()
        self.assertEqual(res, {"type": "text", "text": ""})

if __name__ == "__main__":
    unittest.main()
