# Hotspot Share

<p align="center">
  <img src="assets/icons/hicolor/128x128/apps/hotspot-share.png" width="112" height="112" alt="Hotspot Share Icon">
</p>

<p align="center">
  <b>Turn your Linux laptop into an instant private sharing hub.</b><br>
  Share files, clipboard text, and folders with any device through a browser.<br>
  <i>No cloud servers. No user accounts. No app installation required on the receiving device.</i>
</p>

<p align="center">
  <a href="https://github.com/penguinatnight/hotspot-share/actions/workflows/ci.yml"><img src="https://github.com/penguinatnight/hotspot-share/actions/workflows/ci.yml/badge.svg" alt="CI Status"></a>
  <a href="https://snapcraft.io/hotspot-share"><img src="https://snapcraft.io/hotspot-share/badge.svg" alt="Snap Store"></a>
  <a href="https://github.com/penguinatnight/hotspot-share/releases/latest"><img src="https://img.shields.io/github/v/release/penguinatnight/hotspot-share?label=release&color=blue" alt="GitHub Release"></a>
  <a href="https://github.com/penguinatnight/hotspot-share/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-GPL--3.0-green.svg" alt="License"></a>
  <a href="SECURITY.md"><img src="https://img.shields.io/badge/Telemetry-0%20Bytes-success.svg" alt="Zero Telemetry"></a>
</p>

---

## The 5-Second Pitch

1. **Launch Hotspot Share** on your Linux laptop (Ubuntu, Debian, Fedora, Arch).
2. **Built-in Wi-Fi Hotspot** starts automatically if no local network is available (zero router or internet required).
3. **Scan the pairing QR code** using your iPhone or Android camera.
4. **Browser opens instantly** — beam files, photos, 4K videos, folders, and clipboard snippets with gigabit Wi-Fi 6 speeds.

```text
✓ Built-in Wi-Fi hotspot (works on airplanes, trains, or in parks with no internet)
✓ Zero receiving app (works directly in mobile Safari, Chrome, and Firefox)
✓ 100% offline & zero cloud (0 bytes ever leave your local physical network)
✓ Bi-directional clipboard sharing (text & photos into desktop Ctrl+V buffer)
✓ High-speed 8MB chunked transfer engine with RFC 206 range resume support
✓ Full folder tree uploads & on-the-fly streaming ZIP downloads
✓ Protected by PIN pairing, directory sandboxing, and optional TLS/HTTPS encryption
✓ 100% Free & Open Source (GPL-3.0) with zero PyPI dependencies
```

---

## Why Hotspot Share? (Comparison)

| Capability | **Hotspot Share** | Apple AirDrop | LocalSend | Snapdrop | KDE Connect |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Linux ⇄ iPhone** | **Yes (Any Browser)** | :x: | Requires App | WebRTC | Unofficial |
| **Linux ⇄ Android** | **Yes (Any Browser)** | :x: | Requires App | WebRTC | Requires App |
| **Works with No Internet / No Router** | **Yes (Built-in Hotspot)** | Apple-only | :x: Needs Wi-Fi | :x: Needs Web | :x: Needs Wi-Fi |
| **Zero App on Receiving Device** | **Yes (Camera QR)** | Built-in (iOS) | :x: | Yes | :x: |
| **Bi-directional Clipboard (Text & Photos)** | **Yes** | Apple-only | Yes (with app) | Text-only | Yes (with app) |
| **Gigabit Streaming Engine** | **Yes (8MB Chunks)** | High | High | Low (WebRTC) | Medium |
| **Cloud Independence** | **100% Local** | iCloud Auth | 100% Local | STUN/TURN | 100% Local |

The integrated **one-click Linux hotspot controller** + **zero-install browser bridge** is the differentiator: you never have to ask a colleague or friend to install an app just to send a file.

---

## Device Compatibility Matrix

| Host (Linux Laptop / PC) | Companion Device | Supported Browsers | Native App Needed? | Transport |
| :--- | :--- | :--- | :---: | :--- |
| **Linux** (Ubuntu, Fedora, Arch, Debian) | **iPhone / iPad (iOS 15+)** | Safari, Chrome, Firefox, Orion | **None (0 Install)** | Local Wi-Fi / Hotspot |
| **Linux** | **Android Phones & Tablets** | Chrome, Samsung Internet, Firefox | **None (0 Install)** | Local Wi-Fi / Hotspot |
| **Linux** | **Windows 10 / 11** | Edge, Chrome, Firefox, Brave | **None (0 Install)** | Local Wi-Fi / Hotspot |
| **Linux** | **macOS (MacBook / iMac)** | Safari, Chrome, Arc, Firefox | **None (0 Install)** | Local Wi-Fi / Hotspot |
| **Linux** | **Linux Peer** | Any browser or native client | **Optional** | Local Wi-Fi / Hotspot |

---

## Security, Privacy & Threat Model

Technical Linux users ask the right question first: **"Why should I trust this?"**

* **Zero Telemetry Guarantee**: Exactly **0 bytes** ever leave your local computer. There are no analytics pings, no cloud telemetry, and no tracking pixels.
* **Directory Boundary Sandboxing**: The server jails all file requests to `~/HotspotShare` using Python's `pathlib.Path.resolve().is_relative_to()`. Any attempt to traverse directories (`../`) or follow untrusted symlinks is blocked with HTTP 403.
* **Cryptographic PIN Pairing**: High-entropy 4-digit PIN generated via Python's standard `secrets` module. Timing-attack protected via `secrets.compare_digest()`. IP brute-force throttled after 5 attempts.
* **Least Privilege**: Remote peer devices **cannot delete files** on the host. The `/api/delete` endpoint strictly verifies `is_client_local()`.
* **Verified Zero External Python Dependencies**: The backend runs purely on the audited Python 3 standard library (`http.server`, `socket`, `threading`, `secrets`, `pathlib`).

Read the full threat model in [`SECURITY.md`](SECURITY.md).

---

## Installation

### Method 1: Canonical Snap Store (Recommended on Ubuntu)

Available directly in **Ubuntu App Center** or via terminal:

```bash
sudo snap install hotspot-share
```

### Method 2: Debian / Ubuntu Package (.deb)

Download the `.deb` from the [latest GitHub Release](https://github.com/penguinatnight/hotspot-share/releases/latest) and install:

```bash
sudo apt install ./hotspot-share_*_amd64.deb
```

### Method 3: From Source (Quick User Install)

```bash
git clone https://github.com/penguinatnight/hotspot-share.git
cd hotspot-share
make install-user
hotspot-share-gui
```

---

## Usage

### Desktop Graphical Interface
Launch **Hotspot Share** from your application menu or terminal:
```bash
hotspot-share-gui
```

### Headless Server / CLI Mode
For servers, homelabs, or SSH terminal workflows:
```bash
# Start server on dynamic port
hotspot-share

# Start on port 9000 with a custom directory
hotspot-share -p 9000 -d ~/MyTransfers

# Enable 4-digit PIN pairing security
hotspot-share --auth

# Enable ephemeral TLS/HTTPS encryption
hotspot-share --ssl

# Automatically create a Wi-Fi hotspot named "LinuxShare"
hotspot-share --hotspot LinuxShare
```

---

## Automated Test Suite

Hotspot Share includes 58 automated unit tests covering cryptographic authorization, chunked resumable transfers, security boundaries, and discovery:

```bash
make test
```

---

## Contributing

We welcome pull requests, security audits, and issue reports. Please see [`CONTRIBUTING.md`](CONTRIBUTING.md) for local development guidelines.

---

## License

Licensed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**. See [`LICENSE`](LICENSE) for details.
