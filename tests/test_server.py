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

class DummyHandler:
    def __init__(self, shared_dir):
        self.shared_dir = shared_dir

class TestServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="hotspot_test_share_")
        cls.shared_path = Path(cls.temp_dir)
        HotspotHandler.shared_dir = cls.shared_path
        HotspotHandler.primary_ip = "127.0.0.1"

        # Find an open port
        cls.port = 18880
        for p in range(18880, 18900):
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

    def test_path_traversal_resolution(self):
        dummy = DummyHandler(self.shared_path)

        # Valid relative paths
        self.assertIsNotNone(HotspotHandler.resolve_safe_path(dummy, "foo.txt"))
        self.assertIsNotNone(HotspotHandler.resolve_safe_path(dummy, "sub/dir/bar.txt"))
        self.assertIsNotNone(HotspotHandler.resolve_safe_path(dummy, ""))
        self.assertIsNotNone(HotspotHandler.resolve_safe_path(dummy, "."))

        # Malicious traversal attempts
        self.assertIsNone(HotspotHandler.resolve_safe_path(dummy, "../../../etc/passwd"))
        self.assertIsNone(HotspotHandler.resolve_safe_path(dummy, ".."))
        self.assertIsNone(HotspotHandler.resolve_safe_path(dummy, "../"))

        # Prefix collision attack (e.g. /share_extra when base is /share)
        fake_neighbor = self.shared_path.parent / (self.shared_path.name + "_extra")
        rel_neighbor = os.path.relpath(fake_neighbor, self.shared_path)
        self.assertIsNone(HotspotHandler.resolve_safe_path(dummy, rel_neighbor))

    def test_api_status(self):
        req = urllib.request.Request(f"{self.base_url}/api/status")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode('utf-8'))
            self.assertIn("server_url", data)
            self.assertIn("client_ip", data)
            self.assertIn("is_local_client", data)

    def test_upload_and_download_flow(self):
        # 1. Upload
        filename = "test_data.bin"
        content = b"Hello, Hotspot Share World! " * 50
        upload_url = f"{self.base_url}/api/upload?name={filename}&offset=0&totalSize={len(content)}"
        req = urllib.request.Request(upload_url, data=content, method='POST')
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode('utf-8'))
            self.assertEqual(data.get("status"), "ok")

        # 2. Check file exists on disk
        target_file = self.shared_path / filename
        self.assertTrue(target_file.exists())
        self.assertEqual(target_file.read_bytes(), content)

        # 3. List files
        with urllib.request.urlopen(f"{self.base_url}/api/files") as resp:
            items = json.loads(resp.read().decode('utf-8'))
            names = [it['name'] for it in items]
            self.assertIn(filename, names)

        # 4. Download
        download_url = f"{self.base_url}/api/download?path={filename}"
        with urllib.request.urlopen(download_url) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.read(), content)

    def test_upload_resume_with_truncate(self):
        filename = "resumable.bin"
        target_file = self.shared_path / filename
        # Simulate an interrupted upload where 200 bytes were written, but 50 were corrupted/stale
        corrupt_data = b"A" * 150 + b"STALE_CORRUPT"
        target_file.write_bytes(corrupt_data)

        # Resume from offset 100 with new data
        clean_resume = b"B" * 300
        upload_url = f"{self.base_url}/api/upload?name={filename}&offset=100&totalSize=400"
        req = urllib.request.Request(upload_url, data=clean_resume, method='POST')
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)

        # Total size must be exactly 400 (100 preserved + 300 new, stale data truncated)
        self.assertEqual(target_file.stat().st_size, 400)
        final_content = target_file.read_bytes()
        self.assertEqual(final_content[:100], b"A" * 100)
        self.assertEqual(final_content[100:], clean_resume)

    def test_range_requests(self):
        filename = "range_test.txt"
        target_file = self.shared_path / filename
        content = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        target_file.write_bytes(content)

        req = urllib.request.Request(f"{self.base_url}/api/download?path={filename}")
        req.add_header('Range', 'bytes=10-19')
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 206)
            self.assertEqual(resp.read(), content[10:20])

    def test_mkdir_and_delete(self):
        # Create folder
        mkdir_url = f"{self.base_url}/api/mkdir?name=my_folder"
        req = urllib.request.Request(mkdir_url, method='POST')
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
        self.assertTrue((self.shared_path / "my_folder").is_dir())

        # Disallow malicious mkdir
        bad_mkdir = f"{self.base_url}/api/mkdir?name=../evil_folder"
        req_bad = urllib.request.Request(bad_mkdir, method='POST')
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req_bad)
        self.assertEqual(ctx.exception.code, 400)

        # Delete folder
        del_url = f"{self.base_url}/api/delete?path=my_folder"
        req_del = urllib.request.Request(del_url, method='POST')
        with urllib.request.urlopen(req_del) as resp:
            self.assertEqual(resp.status, 200)
        self.assertFalse((self.shared_path / "my_folder").exists())

        # Disallow deleting shared base folder
        req_del_base = urllib.request.Request(f"{self.base_url}/api/delete?path=", method='POST')
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req_del_base)
        self.assertEqual(ctx.exception.code, 404)

    def test_auth_configure_endpoint(self):
        # Configure PIN: Enable
        url = f"{self.base_url}/api/auth/configure"
        data = json.dumps({"action": "enable"}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            res = json.loads(resp.read().decode("utf-8"))
            self.assertTrue(res["auth_enabled"])
            self.assertEqual(len(res["pin_code"]), 8)
            self.assertEqual(len(res["formatted_pin"]), 9) # "XXXX XXXX"

        # Configure PIN: Regenerate
        data = json.dumps({"action": "regenerate"}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            res = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(len(res["pin_code"]), 8)

        # Configure PIN: Set Custom 8-digit
        data = json.dumps({"action": "set_pin", "pin": "88776655"}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            res = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(res["pin_code"], "88776655")
            self.assertEqual(res["formatted_pin"], "8877 6655")

        # Configure PIN: Disable
        data = json.dumps({"action": "disable"}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            res = json.loads(resp.read().decode("utf-8"))
            self.assertFalse(res["auth_enabled"])

if __name__ == "__main__":
    unittest.main()
