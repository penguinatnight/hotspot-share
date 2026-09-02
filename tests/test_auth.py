import sys
import time
import unittest
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotspot_share.auth import AuthManager

class TestAuthManager(unittest.TestCase):
    def setUp(self):
        AuthManager.disable_pin_auth()

    def tearDown(self):
        AuthManager.disable_pin_auth()

    def test_enable_pin_auth_random(self):
        pin = AuthManager.enable_pin_auth()
        self.assertTrue(AuthManager.auth_enabled)
        self.assertEqual(len(pin), 8)
        self.assertTrue(pin.isdigit())
        self.assertEqual(AuthManager.pin_code, pin)
        self.assertEqual(len(AuthManager.get_formatted_pin()), 9) # "XXXX XXXX"

    def test_enable_pin_auth_custom(self):
        pin = AuthManager.enable_pin_auth("7890")
        self.assertEqual(pin, "7890")
        self.assertEqual(AuthManager.pin_code, "7890")

    def test_verify_pin_success(self):
        AuthManager.enable_pin_auth("1234")
        ok, token = AuthManager.verify_pin("1234", "192.168.1.50")
        self.assertTrue(ok)
        self.assertTrue(isinstance(token, str))
        self.assertEqual(len(token), 32)
        self.assertTrue(AuthManager.is_authorized("192.168.1.50", token))
        self.assertFalse(AuthManager.is_authorized("192.168.1.50", "wrongtoken"))

    def test_verify_pin_invalid(self):
        AuthManager.enable_pin_auth("1234")
        ok, reason = AuthManager.verify_pin("9999", "192.168.1.51")
        self.assertFalse(ok)
        self.assertNotEqual(reason, "rate-limited")

    def test_rate_limiting_brute_force_lockout(self):
        AuthManager.enable_pin_auth("1234")
        ip = "192.168.1.99"
        # 5 failed attempts
        for i in range(5):
            ok, reason = AuthManager.verify_pin("0000", ip)
            self.assertFalse(ok)

        # 6th attempt should be rate-limited immediately even if correct PIN
        ok, reason = AuthManager.verify_pin("1234", ip)
        self.assertFalse(ok)
        self.assertEqual(reason, "rate-limited")

        # Different IP should NOT be locked out
        ok2, token2 = AuthManager.verify_pin("1234", "192.168.1.100")
        self.assertTrue(ok2)

    def test_concurrent_verify_thread_safety(self):
        AuthManager.enable_pin_auth("5555")
        results = []

        def worker(idx):
            ip = f"10.0.0.{idx}"
            ok, tok = AuthManager.verify_pin("5555", ip)
            results.append((ok, tok))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(results), 20)
        self.assertTrue(all(ok for ok, tok in results))
        self.assertEqual(len(set(tok for ok, tok in results)), 20)

if __name__ == "__main__":
    unittest.main()
