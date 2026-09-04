import unittest
import socket
import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotspot_share.discovery import (
    DiscoveryBeacon, MAGIC_HEADER, start_discovery_beacon, stop_discovery_beacon
)

class TestDiscovery(unittest.TestCase):
    def tearDown(self):
        stop_discovery_beacon()

    def test_discovery_payload(self):
        beacon = DiscoveryBeacon("http://192.168.1.5:8080", "MyLaptop", pin_required=True, port=54321)
        raw = beacon._get_payload()
        data = json.loads(raw.decode("utf-8"))
        self.assertEqual(data["magic"], MAGIC_HEADER)
        self.assertEqual(data["app"], "hotspot-share")
        self.assertEqual(data["name"], "MyLaptop")
        self.assertEqual(data["url"], "http://192.168.1.5:8080")
        self.assertTrue(data["pin_required"])

    def test_discovery_beacon_lifecycle(self):
        # Pick a high port to avoid collision
        test_port = 54321
        beacon = start_discovery_beacon("http://127.0.0.1:8080", "TestPC", False, port=test_port)
        self.assertTrue(beacon.running)
        time.sleep(0.1)

        # Send a discover ping over UDP
        client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_sock.settimeout(1.5)
        try:
            probe = json.dumps({"cmd": "discover"}).encode("utf-8")
            client_sock.sendto(probe, ("127.0.0.1", test_port))
            data, _ = client_sock.recvfrom(2048)
            resp = json.loads(data.decode("utf-8"))
            self.assertEqual(resp["magic"], MAGIC_HEADER)
            self.assertEqual(resp["name"], "TestPC")
            self.assertEqual(resp["url"], "http://127.0.0.1:8080")
            self.assertIn("instance_id", resp)
        finally:
            client_sock.close()
            stop_discovery_beacon()

        self.assertFalse(beacon.running)

    def test_discovery_ignores_announcements(self):
        test_port = 54322
        beacon = start_discovery_beacon("http://127.0.0.1:8080", "TestPC", False, port=test_port)
        self.assertTrue(beacon.running)
        time.sleep(0.1)

        client_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_sock.settimeout(0.5)
        try:
            # Send a passive announcement beacon packet (must NOT trigger any reply)
            announcement = json.dumps({
                "magic": MAGIC_HEADER,
                "app": "hotspot-share",
                "name": "AnotherPeer",
                "url": "http://192.168.1.99:8080"
            }).encode("utf-8")
            client_sock.sendto(announcement, ("127.0.0.1", test_port))

            with self.assertRaises(socket.timeout):
                client_sock.recvfrom(2048)
        finally:
            client_sock.close()
            stop_discovery_beacon()

if __name__ == '__main__':
    unittest.main()
