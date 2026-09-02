import sys
import unittest
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotspot_share.transfers import TransferTracker, format_size

class TestTransfers(unittest.TestCase):
    def setUp(self):
        with TransferTracker._lock:
            TransferTracker.transfers.clear()
            TransferTracker.cancelled_transfers.clear()

    def test_format_size(self):
        self.assertEqual(format_size(0), "0 B")
        self.assertEqual(format_size(512), "512 B")
        self.assertEqual(format_size(1024), "1.0 KB")
        self.assertEqual(format_size(1024 * 1024), "1.0 MB")
        self.assertEqual(format_size(5 * 1024 * 1024 * 1024), "5.0 GB")

    def test_transfer_lifecycle(self):
        tx_id = "tx_123"
        TransferTracker.start_transfer(tx_id, "video.mp4", "videos/video.mp4", 1000000, "192.168.1.5", "Phone")
        self.assertFalse(TransferTracker.is_cancelled(tx_id))

        TransferTracker.update_progress(tx_id, 500000)
        state = TransferTracker.get_transfers_state()
        self.assertEqual(len(state), 1)
        self.assertEqual(state[0]["id"], tx_id)
        self.assertEqual(state[0]["progress_pct"], 50)

        TransferTracker.finish_transfer(tx_id, success=True)
        state2 = TransferTracker.get_transfers_state()
        self.assertEqual(state2[0]["status"], "completed")

    def test_transfer_cancel(self):
        tx_id = "tx_456"
        TransferTracker.start_transfer(tx_id, "file.zip", "file.zip", 2000000, "192.168.1.10", "Phone")
        TransferTracker.cancel_transfer(tx_id)
        self.assertTrue(TransferTracker.is_cancelled(tx_id))

        TransferTracker.finish_transfer(tx_id, success=False, error_msg="Cancelled", is_cancelled=True)
        state = TransferTracker.get_transfers_state()
        self.assertEqual(state[0]["status"], "cancelled")

    def test_cancel_all(self):
        for i in range(5):
            TransferTracker.start_transfer(f"tx_{i}", f"f_{i}.txt", f"f_{i}.txt", 1000, "192.168.1.10", "Phone")
        TransferTracker.cancel_all()
        for i in range(5):
            self.assertTrue(TransferTracker.is_cancelled(f"tx_{i}"))

if __name__ == "__main__":
    unittest.main()
