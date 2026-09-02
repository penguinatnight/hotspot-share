import unittest
import os
import ssl
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hotspot_share.crypto_ssl import generate_ephemeral_ssl_cert, create_ssl_context

class TestSSL(unittest.TestCase):
    def test_generate_ephemeral_ssl_cert(self):
        cert_path, key_path, temp_dir = generate_ephemeral_ssl_cert("test-host.local")
        try:
            self.assertTrue(os.path.exists(cert_path))
            self.assertTrue(os.path.exists(key_path))
            self.assertTrue(os.path.exists(temp_dir))

            # Verify permissions: private key should be 0600
            key_stat = os.stat(key_path)
            self.assertEqual(oct(key_stat.st_mode)[-3:], "600")

            # Verify context creation from files
            ctx = create_ssl_context(cert_path, key_path)
            self.assertIsInstance(ctx, ssl.SSLContext)
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_create_ssl_context_ephemeral(self):
        ctx = create_ssl_context()
        self.assertIsInstance(ctx, ssl.SSLContext)

if __name__ == '__main__':
    unittest.main()
