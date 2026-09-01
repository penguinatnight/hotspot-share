# Hotspot Share

<p align="center">
  <img src="assets/icons/hicolor/128x128/apps/hotspot-share.png" width="128" height="128" alt="Hotspot Share Icon">
</p>

<p align="center">
  <b>High-Speed Local Wi-Fi File Sharing & Multimodal Clipboard Sync for Ubuntu / Linux & Mobile</b><br>
  <i>Zero Cloud. Zero App Installation on Phones. Zero Python External Dependencies.</i>
</p>

<p align="center">
  <a href="https://github.com/penguinatnight/hotspot-share/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-GPL--3.0-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/Platform-Linux%20%7C%20Android%20%7C%20iOS-informational.svg" alt="Platforms">
  <img src="https://img.shields.io/badge/Ubuntu%20App%20Center-Ready-orange.svg" alt="Ubuntu App Center">
  <img src="https://img.shields.io/badge/Confinement-Strict-green.svg" alt="Confinement">
</p>

---

## Overview

**Hotspot Share** is a modern, high-throughput local network file transfer and clipboard bridge built specifically for Linux desktops (Ubuntu, Debian, Fedora, Arch) and mobile smartphones (Android, iPhone).

Instead of forcing users to install mobile apps or upload private files to third-party cloud servers, Hotspot Share spins up an optimized, local HTTP/1.1 micro-server with WebKit native desktop integration. Mobile devices simply scan an interactive QR code to immediately transfer gigabytes of files, stream whole directory trees as zip archives on-the-fly, or synchronize clipboard contents directly into the Linux PC's `Ctrl+V` buffer.

---

## Key Features

- **⚡ High-Throughput Chunked Transfers**: Tuned 8MB socket buffers for Wi-Fi 6 speeds (40–90+ MB/s over 5GHz Hotspots).
- **🔄 Auto-Resumable Uploads & Downloads**: Interrupted mobile uploads automatically resume from the exact byte offset.
- **📋 Bi-Directional Clipboard Sync**:
  - Send text or raw images (PNG/JPEG) from mobile to Linux clipboard for immediate `Ctrl+V` pasting in Discord, GIMP, Slack, LibreOffice, or terminal.
  - Pull text or images copied on Linux directly to mobile.
- **📦 Streaming Folder Downloads (Zip-on-the-Fly)**: Download entire directories as `.zip` archives with real-time compression streaming.
- **🔒 Optional PIN Pairing Security**: Set a 4-digit PIN for safe sharing on public or semi-trusted Wi-Fi networks.
- **📶 Built-in Wi-Fi Hotspot Automation**: Directly control NetworkManager to start/stop an Ubuntu Access Point and generate instant Wi-Fi join QR codes (`WIFI:T:WPA;S:...;P:...;;`).
- **🖥️ Native Desktop Integration**:
  - System Tray / AppIndicator status menu with background minimizing.
  - Native Desktop Notifications via `libnotify` / Desktop Portal for incoming transfers.
  - Nautilus / Nemo right-click file context menu: *"Send via Hotspot Share"*.
- **📱 Zero Phone App Installation (PWA)**: Mobile client is a Progressive Web App (PWA) with responsive dark/light glassmorphic UI.

---

## Project Structure

```
hotspot-share/
├── assets/
│   ├── icons/                   # Standard FreeDesktop hicolor icons (16x16 to 512x512 & SVG)
│   └── screenshots/             # Store listing screenshots
├── extensions/
│   └── nautilus/                # Nautilus right-click context menu extension
├── gui/
│   ├── gui.c                    # Native GTK3 / WebKit2GTK desktop launcher
│   └── hotspot-share-gui        # Compiled native executable
├── packaging/
│   ├── appstream/               # AppStream 1.0 metadata (org.yab.hotspotshare.metainfo.xml)
│   ├── debian/                  # Debian package control, rules, and changelog
│   ├── desktop/                 # XDG desktop entry (hotspot-share.desktop)
│   ├── flatpak/                 # Flathub Flatpak manifest
│   └── snap/                    # Ubuntu Snapcraft recipe (snapcraft.yaml)
├── src/
│   └── hotspot_share/           # Modular Python backend
│       ├── __init__.py
│       ├── auth.py              # PIN pairing & token authorization
│       ├── cli.py               # CLI entrypoint and terminal dashboard
│       ├── clipboard.py         # Cross-desktop Wayland / X11 clipboard engine
│       ├── config.py            # XDG directories & runtime path resolver
│       ├── devices.py           # Device tracker & model heuristics
│       ├── hotspot.py           # NetworkManager AP controller
│       ├── notifications.py     # Desktop notification manager
│       ├── qr.py                # ISO/IEC 18004 pure-Python QR generator
│       ├── server.py            # High-throughput HTTP server & API
│       └── transfers.py         # Live progress & transfer tracker
├── web/
│   ├── app.js                   # Frontend JavaScript transfer engine
│   ├── index.html               # Responsive web UI template
│   ├── manifest.json            # PWA manifest
│   └── style.css                # Modern glassmorphism CSS
├── install.sh                   # 1-command installer script
├── Makefile                     # Build & installation targets
└── setup.py                     # Python package definition
```

---

## Installation

### Method 1: 1-Command Installer (Recommended)

```bash
git clone https://github.com/penguinatnight/hotspot-share.git
cd hotspot-share
./install.sh
```

### Method 2: Manual Makefile Build

```bash
# Install build dependencies on Ubuntu / Debian:
sudo apt install -y gcc pkg-config libgtk-3-dev libwebkit2gtk-4.1-dev python3 wl-clipboard

# Compile and install for current user:
make install-user

# Or install system-wide (requires root):
sudo make install
```

---

## Usage

### Launching the Desktop UI
Launch **Hotspot Share** from your application menu or run:
```bash
hotspot-share-gui
```

### Running in Headless Server Mode (CLI)
For servers, headless setups, or terminal enthusiasts:
```bash
# Start default server on dynamic port
hotspot-share

# Start on port 9000 saving to a custom directory
hotspot-share -p 9000 -d ~/MySharedFiles

# Enable 4-digit PIN pairing security
hotspot-share --auth

# Automatically create a Wi-Fi hotspot named "MyLaptopHotspot"
hotspot-share --hotspot MyLaptopHotspot
```

---

## Ubuntu App Center / Snap Publishing Guide

To build and publish to the official **Ubuntu App Center**:

1. **Test the Snap package locally**:
   ```bash
   sudo snap install snapcraft --classic
   snapcraft --destructive-mode
   sudo snap install hotspot-share_2.0.0_amd64.snap --dangerous
   ```

2. **Register the app name on Snapcraft**:
   ```bash
   snapcraft login
   snapcraft register hotspot-share
   ```

3. **Upload to Candidate Channel**:
   ```bash
   snapcraft upload --release=candidate hotspot-share_2.0.0_amd64.snap
   ```

---

## License

This project is licensed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**. See [`LICENSE`](LICENSE) for details.
