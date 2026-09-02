import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotspot_share.config import (
    get_runtime_dir, write_runtime_info, read_runtime_info,
    clear_runtime_info, get_default_share_dir, get_web_dir
)

class TestConfig(unittest.TestCase):
    def test_runtime_dir_security(self):
        rdir = get_runtime_dir()
        self.assertTrue(rdir.exists())
        mode = oct(rdir.stat().st_mode & 0o777)
        self.assertEqual(mode, oct(0o700))

    def test_runtime_info_atomic_write_read_and_clear(self):
        clear_runtime_info()
        empty_info = read_runtime_info()
        self.assertEqual(empty_info, {})

        write_runtime_info(port=8888, primary_ip="192.168.1.100", url="http://192.168.1.100:8888", token="1234", pid=99999)
        info = read_runtime_info()
        self.assertEqual(info.get("port"), 8888)
        self.assertEqual(info.get("primary_ip"), "192.168.1.100")
        self.assertEqual(info.get("token"), "1234")
        self.assertEqual(info.get("status"), "running")

        clear_runtime_info()
        self.assertEqual(read_runtime_info(), {})

    def test_default_share_dir_exists(self):
        share_dir = get_default_share_dir()
        self.assertTrue(isinstance(share_dir, Path))
        self.assertTrue(share_dir.exists())

    def test_get_web_dir_exists(self):
        web_dir = get_web_dir()
        self.assertTrue(web_dir.exists())
        self.assertTrue((web_dir / "index.html").exists())

if __name__ == "__main__":
    unittest.main()
