import sys
import unittest
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotspot_share.devices import (
    DeviceTracker, get_pc_device_name, is_local_ip,
    save_device_name, load_saved_devices
)

class TestDevices(unittest.TestCase):
    def setUp(self):
        with DeviceTracker._lock:
            DeviceTracker.active_sessions.clear()

    def test_local_ip_detection(self):
        self.assertTrue(is_local_ip("127.0.0.1"))
        self.assertTrue(is_local_ip("::1"))
        self.assertTrue(is_local_ip("localhost"))
        self.assertFalse(is_local_ip("192.168.1.50"))
        self.assertFalse(is_local_ip("10.0.0.5"))

    def test_device_heartbeat_and_registration(self):
        ip = "192.168.1.15"
        is_new = DeviceTracker.register_heartbeat(
            client_ip=ip,
            ua="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
            model="iPhone 15 Pro",
            nickname="Alex's iPhone"
        )
        self.assertTrue(is_new)

        # Immediate second heartbeat should NOT be new
        is_new_2 = DeviceTracker.register_heartbeat(client_ip=ip)
        self.assertFalse(is_new_2)

        phones = DeviceTracker.get_connected_phones()
        self.assertEqual(len(phones), 1)
        self.assertEqual(phones[0]["ip"], ip)
        self.assertEqual(phones[0]["device_name"], "Alex's iPhone")

    def test_pc_name_fallback(self):
        pc_name = get_pc_device_name()
        self.assertTrue(isinstance(pc_name, str))
        self.assertTrue(len(pc_name) > 0)

    def test_concurrent_heartbeats(self):
        def ping(i):
            ip = f"192.168.1.{i}"
            DeviceTracker.register_heartbeat(ip, model=f"Phone {i}")

        threads = [threading.Thread(target=ping, args=(i,)) for i in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        phones = DeviceTracker.get_connected_phones()
        self.assertEqual(len(phones), 30)

if __name__ == "__main__":
    unittest.main()
