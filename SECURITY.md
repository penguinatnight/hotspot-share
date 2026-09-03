# Security Policy & Threat Model

Hotspot Share is built on a single core principle: **Your personal data, files, and clipboard must never leave your local physical control.**

This document provides a transparent, verifiable threat model and security architecture so security auditors and users can inspect exactly how the software behaves.

---

## 1. Zero-Telemetry Guarantee

* **Zero Cloud Network Calls**: Hotspot Share never pings external servers, cloud databases, crash reporters, or analytics endpoints.
* **0 Bytes to the Internet**: All HTTP/HTTPS traffic is strictly confined to `127.0.0.1` and your local private Wi-Fi subnet (`10.42.0.0/24` or `192.168.x.x`).
* **Zero Accounts / Zero Data Retention**: There are no account sign-ups, no user tracking IDs, and no server-side telemetry.

---

## 2. Threat Model & Security Architecture

### A. Local Network Isolation
* **Scenario**: Untrusted devices on the local Wi-Fi or public hotspot.
* **Mitigation**:
  1. **PIN Pairing (Default)**: A cryptographically random 4-digit PIN is generated via Python's `secrets.choice()` on application startup.
  2. **Timing-Attack Resistant**: PIN comparison uses `secrets.compare_digest()` to prevent side-channel timing analysis.
  3. **Brute-Force Rate Limiting**: Client IPs are throttled after 5 failed authentication attempts with exponential backoff.
  4. **Ephemeral Authorization Tokens**: Successful pairing issues a high-entropy 128-bit hex token stored only in memory and valid for that session.

### B. Directory Traversal Sandboxing
* **Scenario**: Malicious peer attempts to upload or download files outside the shared directory (e.g. `../../etc/shadow`).
* **Mitigation**:
  * Every file path is normalized and verified using Python `pathlib.Path.resolve()`.
  * The canonical path must satisfy `path.is_relative_to(shared_dir)`.
  * Paths containing null bytes (`\0`), traversal markers (`..`), or pointing to symlinks outside the sandbox are immediately rejected with HTTP 403 Forbidden.

### C. Principle of Least Privilege
* **Remote File Deletion Blocked by Default**: Remote phone or peer devices **cannot delete files** from the host PC. The `/api/delete` endpoint strictly verifies `is_client_local()`. Remote deletion is rejected unless the host administrator explicitly enables `HOTSPOT_ALLOW_REMOTE_DELETE=1`.
* **Dedicated Shared Directory**: Hotspot Share operates exclusively inside `~/HotspotShare` by default, never exposing your entire home directory.
* **In-Flight Encryption (HTTPS/TLS)**: Ephemeral self-signed SSL/TLS certificates can be activated via `--ssl` for encrypted Wi-Fi transfers.

---

## 3. Supported Versions

| Version | Supported | Security Updates |
| :--- | :---: | :--- |
| 2.0.x | :white_check_mark: | Active support & patches |
| 1.x | :x: | End of life |

---

## 4. Reporting a Vulnerability

If you discover a security issue or vulnerability in Hotspot Share:

1. **Do not create a public GitHub issue.**
2. Email the maintainer directly at: **penguinatnight1@gmail.com** with the subject `[SECURITY] Hotspot Share Vulnerability`.
3. Include:
   * A description of the vulnerability and attack vector.
   * Reproduction steps or proof-of-concept script.
   * Suggested remediation, if known.
4. We acknowledge reports within **24 hours** and aim to release a patched build within **72 hours**.
