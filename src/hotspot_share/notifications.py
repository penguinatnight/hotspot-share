import subprocess
import shutil
from .config import get_icon_file

def notify(title: str, message: str, urgency: str = "normal", icon_path: str = None):
    if not shutil.which("notify-send"):
        return

    icon_p = get_icon_file(128)
    icon = icon_path or (str(icon_p) if icon_p else "")
    cmd = [
        "notify-send",
        "-a", "Hotspot Share",
        "-u", urgency,
        title,
        message
    ]
    if icon:
        cmd.extend(["-i", icon])

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def notify_device_connected(device_name: str):
    notify(
        "Device Connected",
        f"📱 {device_name} is now connected.",
        urgency="low"
    )

def notify_transfer_completed(filename: str, size_str: str = ""):
    extra = f" ({size_str})" if size_str else ""
    notify(
        "File Received",
        f"📥 Saved {filename}{extra}",
        urgency="normal"
    )

def notify_clipboard_synced(summary: str):
    notify(
        "Clipboard Synced",
        f"📋 {summary}",
        urgency="low"
    )
