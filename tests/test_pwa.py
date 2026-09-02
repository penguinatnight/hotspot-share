import unittest
import json
import urllib.request
import tempfile
import shutil
import threading
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotspot_share.server import ThreadedHTTPServer, HotspotHandler
from hotspot_share.config import get_web_dir

class TestPWA(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(tempfile.mkdtemp(prefix="test_pwa_"))
        HotspotHandler.shared_dir = cls.test_dir
        HotspotHandler.primary_ip = "127.0.0.1"
        HotspotHandler.server_port = 8991

        cls.server = ThreadedHTTPServer(('127.0.0.1', 8991), HotspotHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_manifest_file_validity(self):
        web_dir = get_web_dir()
        manifest_file = web_dir / "manifest.json"
        self.assertTrue(manifest_file.exists(), "manifest.json must exist in web/")
        
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
        self.assertIn("name", data)
        self.assertIn("short_name", data)
        self.assertIn("start_url", data)
        self.assertIn("display", data)
        self.assertEqual(data["display"], "standalone")
        self.assertIn("icons", data)
        self.assertGreaterEqual(len(data["icons"]), 2)

    def test_service_worker_file_validity(self):
        web_dir = get_web_dir()
        sw_file = web_dir / "sw.js"
        self.assertTrue(sw_file.exists(), "sw.js must exist in web/")
        content = sw_file.read_text(encoding="utf-8")
        self.assertIn("addEventListener", content)
        self.assertIn("install", content)
        self.assertIn("fetch", content)

    def test_manifest_endpoint(self):
        req = urllib.request.Request("http://127.0.0.1:8991/manifest.json")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("application/manifest+json", resp.headers.get("Content-Type", ""))
            body = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(body.get("name"), "Hotspot Share")

    def test_service_worker_endpoint(self):
        req = urllib.request.Request("http://127.0.0.1:8991/sw.js")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIn("application/javascript", resp.headers.get("Content-Type", ""))
            self.assertEqual(resp.headers.get("Service-Worker-Allowed"), "/")

    def test_pwa_icons_endpoint(self):
        for icon in ("/icon-192.png", "/icon-512.png"):
            req = urllib.request.Request(f"http://127.0.0.1:8991{icon}")
            with urllib.request.urlopen(req) as resp:
                self.assertEqual(resp.status, 200)
                self.assertEqual(resp.headers.get("Content-Type"), "image/png")
                self.assertGreater(len(resp.read()), 100)

if __name__ == '__main__':
    unittest.main()
