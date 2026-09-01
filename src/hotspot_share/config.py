import os
import sys
import json
from pathlib import Path

APP_NAME = "hotspot-share"
APP_DISPLAY_NAME = "Hotspot Share"
APP_ID = "org.yab.hotspotshare"

def get_config_dir() -> Path:
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        base = Path(xdg_config)
    else:
        base = Path.home() / ".config"
    config_dir = base / APP_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

def get_cache_dir() -> Path:
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        base = Path(xdg_cache)
    else:
        base = Path.home() / ".cache"
    cache_dir = base / APP_NAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir

def get_runtime_dir() -> Path:
    xdg_runtime = os.environ.get("XDG_RUNTIME_DIR")
    if xdg_runtime:
        base = Path(xdg_runtime)
    else:
        user = os.environ.get("USER", "default")
        base = Path(f"/tmp/hotspot-share-runtime-{user}")
    runtime_dir = base / APP_NAME
    try:
        runtime_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        fallback = Path.home() / ".cache" / APP_NAME
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
    return runtime_dir

def get_default_share_dir() -> Path:
    # Try XDG download or Desktop
    xdg_download = os.environ.get("XDG_DOWNLOAD_DIR")
    if xdg_download and Path(xdg_download).exists():
        target = Path(xdg_download) / "HotspotShare"
    elif (Path.home() / "Downloads").exists():
        target = Path.home() / "Downloads" / "HotspotShare"
    elif (Path.home() / "Desktop").exists():
        target = Path.home() / "Desktop" / "from-phone"
    else:
        target = Path.home() / "HotspotShare"
    target.mkdir(parents=True, exist_ok=True)
    return target

def get_web_dir() -> Path:
    # 1. Check relative to source repo (development)
    source_web = Path(__file__).resolve().parent.parent.parent / "web"
    if source_web.exists() and (source_web / "index.html").exists():
        return source_web

    # 2. Check SNAP environment
    snap_path = os.environ.get("SNAP")
    if snap_path:
        snap_web = Path(snap_path) / "share" / APP_NAME / "web"
        if snap_web.exists():
            return snap_web

    # 3. Check standard system locations
    system_paths = [
        Path("/usr/share") / APP_NAME / "web",
        Path("/usr/local/share") / APP_NAME / "web",
        Path.home() / ".local" / "share" / APP_NAME / "web"
    ]
    for p in system_paths:
        if p.exists() and (p / "index.html").exists():
            return p

    return source_web

def get_icon_file(size=512, ext="png") -> Path:
    # 1. Check source repo
    if ext == "svg":
        source_svg = Path(__file__).resolve().parent.parent.parent / "assets" / "icons" / "hotspot-share.svg"
        if source_svg.exists():
            return source_svg
    else:
        source_png = Path(__file__).resolve().parent.parent.parent / "assets" / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "hotspot-share.png"
        if source_png.exists():
            return source_png

    # 2. Check XDG icon dirs
    hicolor_paths = [
        Path.home() / ".local" / "share" / "icons" / "hicolor",
        Path("/usr/share/icons/hicolor"),
        Path("/usr/local/share/icons/hicolor")
    ]
    snap_path = os.environ.get("SNAP")
    if snap_path:
        hicolor_paths.insert(0, Path(snap_path) / "share" / "icons" / "hicolor")

    for base in hicolor_paths:
        if ext == "svg":
            candidate = base / "scalable" / "apps" / "hotspot-share.svg"
            if candidate.exists():
                return candidate
        else:
            candidate = base / f"{size}x{size}" / "apps" / "hotspot-share.png"
            if candidate.exists():
                return candidate

    return Path("")

def write_runtime_info(port: int, primary_ip: str, url: str, token: str = None, pid: int = None):
    r_dir = get_runtime_dir()
    info_file = r_dir / "server.json"
    data = {
        "pid": pid or os.getpid(),
        "port": port,
        "primary_ip": primary_ip,
        "url": url,
        "token": token or "",
        "status": "running"
    }
    try:
        info_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

def read_runtime_info() -> dict:
    r_dir = get_runtime_dir()
    info_file = r_dir / "server.json"
    if info_file.exists():
        try:
            return json.loads(info_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def clear_runtime_info():
    r_dir = get_runtime_dir()
    info_file = r_dir / "server.json"
    if info_file.exists():
        try:
            info_file.unlink(missing_ok=True)
        except Exception:
            pass
