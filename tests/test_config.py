import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotspot_share.config import (
    get_runtime_dir, write_runtime_info, read_runtime_info,
    clear_runtime_info, get_default_share_dir, get_web_dir, get_icon_file
)
import tempfile
import shutil

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

    def test_get_web_dir_snap_usr_share(self):
        tmp_snap = tempfile.mkdtemp(prefix="snap_test_")
        try:
            fake_web = Path(tmp_snap) / "usr" / "share" / "hotspot-share" / "web"
            fake_web.mkdir(parents=True)
            (fake_web / "index.html").write_text("<!DOCTYPE html><html><body>Snap Web</body></html>")

            old_snap = os.environ.get("SNAP")
            os.environ["SNAP"] = tmp_snap
            try:
                resolved = get_web_dir()
                self.assertEqual(resolved, fake_web)
                self.assertTrue((resolved / "index.html").exists())
            finally:
                if old_snap is not None:
                    os.environ["SNAP"] = old_snap
                else:
                    os.environ.pop("SNAP", None)
        finally:
            shutil.rmtree(tmp_snap)

    def test_get_web_dir_snap_share(self):
        tmp_snap = tempfile.mkdtemp(prefix="snap_test_")
        try:
            fake_web = Path(tmp_snap) / "share" / "hotspot-share" / "web"
            fake_web.mkdir(parents=True)
            (fake_web / "index.html").write_text("<!DOCTYPE html><html><body>Snap Share Web</body></html>")

            old_snap = os.environ.get("SNAP")
            os.environ["SNAP"] = tmp_snap
            try:
                resolved = get_web_dir()
                self.assertEqual(resolved, fake_web)
                self.assertTrue((resolved / "index.html").exists())
            finally:
                if old_snap is not None:
                    os.environ["SNAP"] = old_snap
                else:
                    os.environ.pop("SNAP", None)
        finally:
            shutil.rmtree(tmp_snap)

    def test_get_web_dir_env_override(self):
        tmp_env = tempfile.mkdtemp(prefix="env_web_")
        try:
            fake_web = Path(tmp_env) / "custom_web"
            fake_web.mkdir(parents=True)
            (fake_web / "index.html").write_text("<!DOCTYPE html><html><body>Custom Web</body></html>")

            os.environ["HOTSPOT_WEB_DIR"] = str(fake_web)
            try:
                resolved = get_web_dir()
                self.assertEqual(resolved, fake_web)
            finally:
                os.environ.pop("HOTSPOT_WEB_DIR", None)
        finally:
            shutil.rmtree(tmp_env)

    def test_get_icon_file_snap(self):
        tmp_snap = tempfile.mkdtemp(prefix="snap_icon_")
        try:
            icon_dir = Path(tmp_snap) / "usr" / "share" / "icons" / "hicolor" / "512x512" / "apps"
            icon_dir.mkdir(parents=True)
            fake_png = icon_dir / "hotspot-share.png"
            fake_png.write_bytes(b"\x89PNG\r\n\x1a\n")

            old_snap = os.environ.get("SNAP")
            os.environ["SNAP"] = tmp_snap
            try:
                resolved = get_icon_file(512, "png")
                self.assertEqual(resolved, fake_png)
            finally:
                if old_snap is not None:
                    os.environ["SNAP"] = old_snap
                else:
                    os.environ.pop("SNAP", None)
        finally:
            shutil.rmtree(tmp_snap)

if __name__ == "__main__":
    unittest.main()
