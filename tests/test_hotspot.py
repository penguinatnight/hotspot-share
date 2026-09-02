import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotspot_share.hotspot import (
    generate_default_credentials, is_nmcli_available,
    get_active_hotspot, start_hotspot, stop_hotspot
)

class TestHotspot(unittest.TestCase):
    def test_generate_default_credentials(self):
        ssid, password = generate_default_credentials()
        self.assertTrue(ssid.endswith("-Share"))
        self.assertEqual(len(password), 10)
        self.assertTrue(password.isalnum())

    @patch("shutil.which", return_value=None)
    def test_nmcli_missing_behavior(self, mock_which):
        self.assertFalse(is_nmcli_available())
        self.assertEqual(get_active_hotspot(), {"active": False})
        res_start = start_hotspot()
        self.assertEqual(res_start.get("status"), "error")
        res_stop = stop_hotspot()
        self.assertEqual(res_stop.get("status"), "error")

if __name__ == "__main__":
    unittest.main()
