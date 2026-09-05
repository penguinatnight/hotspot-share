import os
import sys
import json
import time
import shutil
import urllib.request
import urllib.error
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotspot_share.server import ThreadedHTTPServer, HotspotHandler
from hotspot_share.auth import AuthManager

class TestSecurityAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="hotspot_sec_test_")
        cls.shared_path = Path(cls.temp_dir) / "shared"
        cls.shared_path.mkdir(parents=True, exist_ok=True)
        HotspotHandler.shared_dir = cls.shared_path
        HotspotHandler.primary_ip = "127.0.0.1"

        cls.port = 19980
        for p in range(19980, 20000):
            try:
                cls.server = ThreadedHTTPServer(('127.0.0.1', p), HotspotHandler)
                cls.port = p
                break
            except OSError:
                continue

        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.server.shutdown()
            cls.server.server_close()
        except Exception:
            pass
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def setUp(self):
        AuthManager.disable_pin_auth()

    def test_dns_rebinding_invalid_host_header_rejected(self):
        req = urllib.request.Request(f"{self.base_url}/api/status")
        req.add_header("Host", "attacker.com:8080")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 403)

    def test_untrusted_origin_rejected(self):
        req = urllib.request.Request(f"{self.base_url}/api/status")
        req.add_header("Origin", "http://evil-website.com")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 403)

    def test_cross_site_sec_fetch_rejected(self):
        req = urllib.request.Request(f"{self.base_url}/api/status")
        req.add_header("Sec-Fetch-Site", "cross-site")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 403)

    def test_no_wildcard_cors_header(self):
        req = urllib.request.Request(f"{self.base_url}/api/status")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            cors = resp.headers.get("Access-Control-Allow-Origin")
            self.assertNotEqual(cors, "*")
            self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")

    def test_download_headers_prevent_inline_html_svg_xss(self):
        html_file = self.shared_path / "payload.html"
        html_file.write_text("<script>alert(1)</script>", encoding="utf-8")

        svg_file = self.shared_path / "payload.svg"
        svg_file.write_text('<svg onload="alert(1)"></svg>', encoding="utf-8")

        req_html = urllib.request.Request(f"{self.base_url}/api/download?path=payload.html")
        with urllib.request.urlopen(req_html) as resp:
            self.assertEqual(resp.status, 200)
            disp = resp.headers.get("Content-Disposition", "")
            self.assertTrue(disp.startswith("attachment"))
            self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
            self.assertIn("sandbox", resp.headers.get("Content-Security-Policy", ""))

        req_svg = urllib.request.Request(f"{self.base_url}/api/download?path=payload.svg")
        with urllib.request.urlopen(req_svg) as resp:
            self.assertEqual(resp.status, 200)
            disp = resp.headers.get("Content-Disposition", "")
            self.assertTrue(disp.startswith("attachment"))
            self.assertIn("sandbox", resp.headers.get("Content-Security-Policy", ""))

    def test_symlink_upload_protection(self):
        outside_file = Path(self.temp_dir) / "sensitive_config.txt"
        outside_file.write_text("SUPER_SECRET_KEY", encoding="utf-8")

        link_inside = self.shared_path / "symlink_test.txt"
        try:
            link_inside.symlink_to(outside_file)
        except OSError:
            return

        upload_content = b"ATTACKER_OVERWRITE"
        upload_url = f"{self.base_url}/api/upload?name=symlink_test.txt&offset=0&totalSize={len(upload_content)}"
        req = urllib.request.Request(upload_url, data=upload_content, method='POST')
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)

        self.assertEqual(outside_file.read_text(encoding="utf-8"), "SUPER_SECRET_KEY")
        self.assertFalse(link_inside.is_symlink())
        self.assertEqual(link_inside.read_bytes(), upload_content)

    def test_range_header_malformed_or_invalid_returns_416(self):
        test_file = self.shared_path / "range_test.txt"
        test_file.write_bytes(b"0123456789abcdefghij")

        invalid_ranges = [
            "bytes=abc-def",
            "bytes=invalid",
            "bytes=50-10",
            "bytes=9999-10000",
            "bytes=-10-5"
        ]
        for rng in invalid_ranges:
            req = urllib.request.Request(f"{self.base_url}/api/download?path=range_test.txt")
            req.add_header("Range", rng)
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req)
            self.assertEqual(ctx.exception.code, 416, f"Failed for range header {rng}")

    def test_delete_symlink_preserves_target_folder(self):
        target_dir = self.shared_path / "real_dir"
        target_dir.mkdir(exist_ok=True)
        (target_dir / "preserve.txt").write_text("DO_NOT_DELETE", encoding="utf-8")

        symlink_dir = self.shared_path / "symlink_dir"
        if symlink_dir.exists():
            symlink_dir.unlink()
        try:
            symlink_dir.symlink_to(target_dir)
        except OSError:
            return

        del_url = f"{self.base_url}/api/delete?path=symlink_dir"
        req = urllib.request.Request(del_url, data=b"", method="POST")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)

        # Symlink should be removed
        self.assertFalse(symlink_dir.exists())
        # Target directory and its file MUST remain intact
        self.assertTrue(target_dir.exists())
        self.assertEqual((target_dir / "preserve.txt").read_text(encoding="utf-8"), "DO_NOT_DELETE")

if __name__ == "__main__":
    unittest.main()
