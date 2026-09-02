import unittest
import tempfile
import shutil
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotspot_share.conflict import resolve_filename_conflict, split_filename_and_ext

class TestConflictResolution(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="test_conflict_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_split_filename_and_ext(self):
        self.assertEqual(split_filename_and_ext("document.pdf"), ("document", ".pdf"))
        self.assertEqual(split_filename_and_ext("archive.tar.gz"), ("archive", ".tar.gz"))
        self.assertEqual(split_filename_and_ext("backup.tar.bz2"), ("backup", ".tar.bz2"))
        self.assertEqual(split_filename_and_ext("README"), ("README", ""))
        self.assertEqual(split_filename_and_ext(".hidden"), (".hidden", ""))

    def test_nonexistent_file_untouched(self):
        p = self.test_dir / "new_file.txt"
        resolved = resolve_filename_conflict(p, strategy="rename")
        self.assertEqual(resolved, p)

    def test_overwrite_strategy(self):
        p = self.test_dir / "existing.txt"
        p.write_text("hello")
        resolved = resolve_filename_conflict(p, strategy="overwrite")
        self.assertEqual(resolved, p)

    def test_rename_strategy_single_conflict(self):
        p = self.test_dir / "photo.jpg"
        p.write_bytes(b"data")
        resolved = resolve_filename_conflict(p, strategy="rename")
        self.assertEqual(resolved, self.test_dir / "photo (1).jpg")

    def test_rename_strategy_multiple_conflicts(self):
        p = self.test_dir / "video.mp4"
        p.write_bytes(b"0")
        (self.test_dir / "video (1).mp4").write_bytes(b"1")
        (self.test_dir / "video (2).mp4").write_bytes(b"2")

        resolved = resolve_filename_conflict(p, strategy="rename")
        self.assertEqual(resolved, self.test_dir / "video (3).mp4")

    def test_rename_strategy_compound_extension(self):
        p = self.test_dir / "data.tar.gz"
        p.write_bytes(b"tar")
        resolved = resolve_filename_conflict(p, strategy="rename")
        self.assertEqual(resolved, self.test_dir / "data (1).tar.gz")

    def test_rename_strategy_no_extension(self):
        p = self.test_dir / "LICENSE"
        p.write_text("MIT")
        resolved = resolve_filename_conflict(p, strategy="rename")
        self.assertEqual(resolved, self.test_dir / "LICENSE (1)")

if __name__ == '__main__':
    unittest.main()
