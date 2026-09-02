import os
import ssl
import shutil
import atexit
import tempfile
import subprocess
from typing import Optional, Tuple

def generate_ephemeral_ssl_cert(common_name: str = "hotspot-share.local") -> Tuple[str, str, str]:
    """
    Generates an ephemeral, secure self-signed X.509 certificate and private key.
    Enables secure context on mobile browsers (allowing camera QR scanning & Web Crypto).
    Automatically unlinks on process exit.
    """
    temp_dir = tempfile.mkdtemp(prefix="hotspot_ssl_")
    os.chmod(temp_dir, 0o700)
    cert_path = os.path.join(temp_dir, "server.crt")
    key_path = os.path.join(temp_dir, "server.key")

    cmd = [
        "openssl", "req", "-x509",
        "-newkey", "rsa:2048",
        "-keyout", key_path,
        "-out", cert_path,
        "-days", "7",
        "-nodes",
        "-subj", f"/CN={common_name}/O=HotspotShare"
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if res.returncode != 0 or not os.path.exists(cert_path):
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError("Failed to generate self-signed SSL certificate with openssl.")

    os.chmod(key_path, 0o600)
    os.chmod(cert_path, 0o644)

    def cleanup():
        shutil.rmtree(temp_dir, ignore_errors=True)

    atexit.register(cleanup)
    return cert_path, key_path, temp_dir

def create_ssl_context(cert_path: Optional[str] = None, key_path: Optional[str] = None) -> ssl.SSLContext:
    """Creates a TLS server SSLContext with modern cipher configuration."""
    if not cert_path or not key_path:
        cert_path, key_path, _ = generate_ephemeral_ssl_cert()

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=cert_path, keyfile=key_path)
    return context
