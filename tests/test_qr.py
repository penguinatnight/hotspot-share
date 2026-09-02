import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotspot_share.qr import (
    generate_qr_matrix, get_terminal_qr, get_svg_qr,
    get_wifi_qr_text, escape_wifi_str
)

class TestQR(unittest.TestCase):
    def test_qr_matrix_generation_version1(self):
        text = "HELLO"
        m = generate_qr_matrix(text, version=1, ec_level='L')
        # Version 1 size: 17 + 4*1 = 21
        self.assertEqual(len(m), 21)
        self.assertEqual(len(m[0]), 21)
        # Check finder pattern in top-left (7x7)
        self.assertEqual(m[0][0], 1)
        self.assertEqual(m[0][6], 1)
        self.assertEqual(m[6][0], 1)
        self.assertEqual(m[6][6], 1)

    def test_qr_matrix_generation_auto_version(self):
        # Short URL
        url = "http://192.168.1.1:8080"
        m = generate_qr_matrix(url, ec_level='M')
        self.assertIn(len(m), [21, 25, 29, 33, 37, 41])

        # Longer URL with token
        long_url = "http://192.168.122.105:8080/?token=0123456789abcdef0123456789abcdef"
        m2 = generate_qr_matrix(long_url, ec_level='M')
        self.assertIn(len(m2), [29, 33, 37, 41])

    def test_terminal_qr_output(self):
        text = "http://10.42.0.1:8080"
        term = get_terminal_qr(text, indent=4)
        self.assertIn("\033[", term)
        lines = term.split("\n")
        self.assertTrue(len(lines) > 5)

    def test_svg_qr_output(self):
        text = "http://10.42.0.1:8080"
        svg = get_svg_qr(text)
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.endswith("</svg>"))
        self.assertIn('<rect x="0" y="0"', svg)
        self.assertIn('fill="#ffffff"', svg)
        self.assertIn('<path d="', svg)

    def test_wifi_qr_escaping(self):
        # Escaping special characters
        self.assertEqual(escape_wifi_str(r"NormalSSID"), "NormalSSID")
        self.assertEqual(escape_wifi_str(r"SSID;with:special\chars"), r"SSID\;with\:special\\chars")

        wifi_nopass = get_wifi_qr_text("HomeNet", "", "NOPASS")
        self.assertEqual(wifi_nopass, "WIFI:T:nopass;S:HomeNet;;;")

        wifi_wpa = get_wifi_qr_text("My Hotspot;1", "p@ss:word", "WPA")
        self.assertIn(r"S:My Hotspot\;1", wifi_wpa)
        self.assertIn(r"P:p@ss\:word", wifi_wpa)

if __name__ == "__main__":
    unittest.main()
