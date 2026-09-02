import unittest
import time
from pathlib import Path
from hotspot_share.server import BeamTracker

class TestBeamsAndOnboarding(unittest.TestCase):
    def setUp(self):
        BeamTracker.beams.clear()
        BeamTracker.dismissed.clear()

    def test_beam_tracker_pc_to_phone(self):
        # PC (127.0.0.1) uploads a file
        BeamTracker.add_beam(
            beam_id="b1",
            name="photo.jpg",
            rel_path="photo.jpg",
            size=1024,
            is_dir=False,
            sender_name="yab",
            sender_ip="127.0.0.1"
        )
        
        # PC viewing /api/status does NOT see its own beam as incoming
        pc_beams = BeamTracker.get_active_beams("127.0.0.1")
        self.assertEqual(len(pc_beams), 0)

        # Phone (192.168.1.50) sees incoming beam from PC
        phone_beams = BeamTracker.get_active_beams("192.168.1.50")
        self.assertEqual(len(phone_beams), 1)
        self.assertEqual(phone_beams[0]["name"], "photo.jpg")
        self.assertEqual(phone_beams[0]["size"], 1024)
        self.assertFalse(phone_beams[0]["is_dir"])

    def test_beam_tracker_folder(self):
        # PC sends a folder
        BeamTracker.add_beam(
            beam_id="b2",
            name="Documents",
            rel_path="Documents",
            size=4096,
            is_dir=True,
            sender_name="yab",
            sender_ip="127.0.0.1"
        )

        phone_beams = BeamTracker.get_active_beams("192.168.1.88")
        self.assertEqual(len(phone_beams), 1)
        self.assertTrue(phone_beams[0]["is_dir"])
        self.assertEqual(phone_beams[0]["name"], "Documents")

    def test_beam_dismissal(self):
        BeamTracker.add_beam(
            beam_id="b3",
            name="report.pdf",
            rel_path="report.pdf",
            size=2048,
            is_dir=False,
            sender_name="yab",
            sender_ip="127.0.0.1"
        )

        self.assertEqual(len(BeamTracker.get_active_beams("192.168.1.77")), 1)
        BeamTracker.dismiss_beam("b3", "192.168.1.77")
        self.assertEqual(len(BeamTracker.get_active_beams("192.168.1.77")), 0)

    def test_beam_expiration(self):
        BeamTracker.add_beam(
            beam_id="b4",
            name="old.txt",
            rel_path="old.txt",
            size=10,
            is_dir=False,
            sender_name="yab",
            sender_ip="127.0.0.1"
        )
        BeamTracker.beams[0]["time"] = time.time() - 700  # Older than 600s
        self.assertEqual(len(BeamTracker.get_active_beams("192.168.1.66")), 0)

    def test_onboarding_html_structure(self):
        html_path = Path("web/index.html")
        self.assertTrue(html_path.exists())
        content = html_path.read_text(encoding="utf-8")

        # Verify Onboarding modal elements
        self.assertIn('id="onboardingOverlay"', content)
        self.assertIn('id="onboard-slide-0"', content)
        self.assertIn('id="onboard-slide-1"', content)
        self.assertIn('id="onboard-slide-2"', content)
        self.assertIn('id="onboard-slide-3"', content)

        # Verify key product messaging
        self.assertIn("AirDrop for Linux", content)
        self.assertIn("100% Private & Open Source", content)
        self.assertIn("No Login or Accounts", content)
        self.assertIn("Zero Data Retention", content)
        self.assertIn("Camera QR Pairing", content)
        self.assertIn("Clipboard & Folder Transfers", content)

        # Verify incoming beam and toolbar elements
        self.assertIn('id="incomingBeamsContainer"', content)
        self.assertIn('id="tourBtn"', content)
        self.assertIn('id="filesTabBadge"', content)
        self.assertIn('id="btnSelectFiles"', content)
        self.assertIn('id="btnSelectFolder"', content)

    def test_onboarding_app_js_methods(self):
        js_path = Path("web/app.js")
        self.assertTrue(js_path.exists())
        js = js_path.read_text(encoding="utf-8")

        # Verify essential functions
        self.assertIn("function triggerDownload(", js)
        self.assertIn("function syncIncomingBeams(", js)
        self.assertIn("function openOnboarding(", js)
        self.assertIn("function finishOnboarding(", js)
        self.assertIn("localStorage.getItem('hotspot_onboarded')", js)

if __name__ == "__main__":
    unittest.main()
