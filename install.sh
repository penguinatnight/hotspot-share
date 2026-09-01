#!/usr/bin/env bash
set -e

# ==============================================================================
# Hotspot Share - Production Installer for Ubuntu / Debian / Linux
# ==============================================================================

BOLD='\033[1m'
GREEN='\033[32m'
BLUE='\033[34m'
YELLOW='\033[33m'
RESET='\033[0m'

echo -e "${BOLD}${BLUE}╔══════════════════════════════════════════════╗${RESET}"
echo -e "${BOLD}${BLUE}║        Hotspot Share 2.0 Installer           ║${RESET}"
echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════╝${RESET}"
echo ""

# 1. Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Python 3 is required. Please install python3.${RESET}"
    exit 1
fi

# 2. Check build toolchain
MISSING_PKGS=()
if ! command -v gcc &> /dev/null; then MISSING_PKGS+=("gcc"); fi
if ! command -v pkg-config &> /dev/null; then MISSING_PKGS+=("pkg-config"); fi

if ! pkg-config --exists gtk+-3.0; then MISSING_PKGS+=("libgtk-3-dev"); fi
if ! pkg-config --exists webkit2gtk-4.1 && ! pkg-config --exists webkit2gtk-4.0; then
    MISSING_PKGS+=("libwebkit2gtk-4.1-dev");
fi

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo -e "${YELLOW}Missing build dependencies: ${MISSING_PKGS[*]}${RESET}"
    if command -v apt &> /dev/null; then
        echo -e "Install them via: ${BOLD}sudo apt install -y ${MISSING_PKGS[*]}${RESET}"
    fi
fi

# 3. Build & Install
echo -e "${BLUE}==>${RESET} Compiling native GTK3/WebKit desktop launcher..."
make build

echo -e "${BLUE}==>${RESET} Installing to ~/.local..."
make install-user

echo ""
echo -e "${GREEN}${BOLD}✓ Hotspot Share installed successfully!${RESET}"
echo -e "You can launch it from your application menu or run:"
echo -e "  ${BOLD}hotspot-share-gui${RESET}  (Native GUI window)"
echo -e "  ${BOLD}hotspot-share${RESET}      (Headless terminal daemon)"
echo ""
