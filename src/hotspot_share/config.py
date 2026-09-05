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
        uid = os.getuid() if hasattr(os, "getuid") else "default"
        base = Path(f"/tmp/hotspot-share-runtime-{uid}")
    runtime_dir = base / APP_NAME
    try:
        runtime_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(runtime_dir, 0o700)
        except OSError:
            pass
    except Exception:
        fallback = Path.home() / ".cache" / APP_NAME
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
    return runtime_dir

def get_user_home() -> Path:
    real_home = os.environ.get("SNAP_REAL_HOME")
    if real_home and Path(real_home).is_dir():
        return Path(real_home)
    return Path.home()

def get_default_share_dir() -> Path:
    user_home = get_user_home()

    # 1. Prioritize Desktop "from-phone" directory (user preferred default)
    desktop = user_home / "Desktop"
    if desktop.is_dir():
        from_phone_space = desktop / "from phone"
        if from_phone_space.is_dir():
            return from_phone_space
        from_phone = desktop / "from-phone"
        from_phone.mkdir(parents=True, exist_ok=True)
        return from_phone

    # 2. Check XDG_DOWNLOAD_DIR env var
    xdg_download = os.environ.get("XDG_DOWNLOAD_DIR")
    if xdg_download and Path(xdg_download).exists():
        target = Path(xdg_download) / "from-phone"
        target.mkdir(parents=True, exist_ok=True)
        return target

    # 3. Check ~/.config/user-dirs.dirs
    user_dirs_file = user_home / ".config" / "user-dirs.dirs"
    if user_dirs_file.is_file():
        try:
            for line in user_dirs_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("XDG_DOWNLOAD_DIR="):
                    val = line.split("=", 1)[1].strip('"\'')
                    val = val.replace("$HOME", str(user_home))
                    p = Path(val)
                    if p.exists():
                        target = p / "from-phone"
                        target.mkdir(parents=True, exist_ok=True)
                        return target
        except Exception:
            pass

    # 4. Fallbacks
    if (user_home / "Downloads").exists():
        target = user_home / "Downloads" / "from-phone"
    else:
        target = user_home / "from-phone"
    target.mkdir(parents=True, exist_ok=True)
    return target

def get_web_dir() -> Path:
    """Resolve the web frontend assets directory across dev, snap, deb, and pip installs."""
    candidates = []

    # 1. Environment variable override (for tests and custom deployments)
    env_web = os.environ.get("HOTSPOT_WEB_DIR")
    if env_web:
        candidates.append(Path(env_web))

    # 2. Check SNAP environment (prioritize snap container paths if running inside snap)
    snap_path = os.environ.get("SNAP")
    if snap_path:
        snap_root = Path(snap_path)
        candidates.extend([
            snap_root / "usr" / "share" / APP_NAME / "web",
            snap_root / "share" / APP_NAME / "web",
            snap_root / "web",
        ])

    # 3. Check within installed python package data (reliable fallback bundled with code)
    pkg_web = Path(__file__).resolve().parent / "web"
    candidates.append(pkg_web)

    # 4. Check canonical Snap current symlink (in case SNAP revision path changed/unmounted)
    snap_current = Path("/snap") / APP_NAME / "current"
    candidates.extend([
        snap_current / "usr" / "share" / APP_NAME / "web",
        snap_current / "share" / APP_NAME / "web",
        snap_current / "web",
    ])

    # 5. Check relative to source repo (development / source checkout)
    source_web = Path(__file__).resolve().parent.parent.parent / "web"
    candidates.append(source_web)

    # 6. Check standard system and user FHS locations
    candidates.extend([
        Path.home() / ".local" / "share" / APP_NAME / "web",
        Path("/usr/share") / APP_NAME / "web",
        Path("/usr/local/share") / APP_NAME / "web",
        Path(sys.prefix) / "share" / APP_NAME / "web",
        Path(sys.prefix) / "local" / "share" / APP_NAME / "web",
    ])

    for p in candidates:
        if p and p.is_dir() and (p / "index.html").is_file():
            return p

    # 7. Fallback: scan candidate directories recursively if needed
    for base in [pkg_web.parent, Path(__file__).resolve().parent.parent.parent]:
        try:
            found = list(base.glob("**/web/index.html"))
            if found:
                return found[0].parent
        except Exception:
            pass

    return pkg_web if pkg_web.is_dir() else source_web

def get_icon_file(size=512, ext="png") -> Path:
    # 1. Prioritize SNAP environment if running inside snap
    snap_path = os.environ.get("SNAP")
    if snap_path:
        snap_root = Path(snap_path)
        if ext == "svg":
            snap_svg = snap_root / "assets" / "icons" / "hotspot-share.svg"
            if snap_svg.is_file():
                return snap_svg
            for p in [snap_root / "usr" / "share" / "icons" / "hicolor" / "scalable" / "apps" / "hotspot-share.svg",
                      snap_root / "share" / "icons" / "hicolor" / "scalable" / "apps" / "hotspot-share.svg"]:
                if p.is_file():
                    return p
        else:
            for p in [snap_root / "usr" / "share" / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "hotspot-share.png",
                      snap_root / "share" / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "hotspot-share.png",
                      snap_root / "meta" / "gui" / "hotspot-share.png"]:
                if p.is_file():
                    return p

    # 2. Check source repo (development)
    if ext == "svg":
        source_svg = Path(__file__).resolve().parent.parent.parent / "assets" / "icons" / "hotspot-share.svg"
        if source_svg.is_file():
            return source_svg
    else:
        source_png = Path(__file__).resolve().parent.parent.parent / "assets" / "icons" / "hicolor" / f"{size}x{size}" / "apps" / "hotspot-share.png"
        if source_png.is_file():
            return source_png

    # 3. Check XDG & system icon dirs
    hicolor_paths = [
        Path.home() / ".local" / "share" / "icons" / "hicolor",
        Path("/usr/share/icons/hicolor"),
        Path("/usr/local/share/icons/hicolor"),
        Path(sys.prefix) / "share" / "icons" / "hicolor",
    ]

    for base in hicolor_paths:
        if ext == "svg":
            candidate = base / "scalable" / "apps" / "hotspot-share.svg"
            if candidate.is_file():
                return candidate
        else:
            candidate = base / f"{size}x{size}" / "apps" / "hotspot-share.png"
            if candidate.is_file():
                return candidate

    return None

def write_runtime_info(port: int, primary_ip: str, url: str, token: str = None, pid: int = None):
    r_dir = get_runtime_dir()
    info_file = r_dir / "server.json"
    temp_file = r_dir / f"server.json.tmp.{os.getpid()}"
    data = {
        "pid": pid or os.getpid(),
        "port": port,
        "primary_ip": primary_ip,
        "url": url,
        "token": token or "",
        "status": "running"
    }
    try:
        temp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temp_file.replace(info_file)
    except Exception:
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
