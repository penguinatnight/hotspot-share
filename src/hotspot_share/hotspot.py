import subprocess
import shutil
import re
import secrets
import string
import socket

def is_nmcli_available() -> bool:
    return shutil.which("nmcli") is not None

def get_wifi_devices() -> list:
    if not is_nmcli_available():
        return []
    try:
        out = subprocess.check_output(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"], text=True)
        wifi_devs = []
        for line in out.splitlines():
            parts = line.strip().split(":")
            if len(parts) >= 3 and parts[1] == "wifi":
                wifi_devs.append({"device": parts[0], "state": parts[2]})
        return wifi_devs
    except Exception:
        return []

def get_active_hotspot() -> dict:
    if not is_nmcli_available():
        return {"active": False}
    try:
        out = subprocess.check_output(["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"], text=True)
        candidates = []
        for line in out.splitlines():
            parts = line.strip().split(":")
            if len(parts) >= 3 and parts[1] in ("802-11-wireless", "wifi"):
                name_low = parts[0].lower()
                if "hotspot" in name_low or "share" in name_low:
                    return {"active": True, "name": parts[0], "device": parts[2]}
                candidates.append((parts[0], parts[2]))

        # If candidates exist, check connection settings for 802-11-wireless.mode ap
        for con_name, dev in candidates:
            try:
                con_mode = subprocess.check_output(
                    ["nmcli", "-t", "-f", "802-11-wireless.mode", "connection", "show", con_name],
                    text=True, stderr=subprocess.DEVNULL
                ).strip()
                if "ap" in con_mode.lower():
                    return {"active": True, "name": con_name, "device": dev}
            except Exception:
                pass
    except Exception:
        pass
    return {"active": False}

def generate_default_credentials():
    host = socket.gethostname().split('.')[0].capitalize()
    ssid = f"{host}-Share"
    chars = string.ascii_letters + string.digits
    password = ''.join(secrets.choice(chars) for _ in range(10))
    return ssid, password

def start_hotspot(ssid: str = None, password: str = None, ifname: str = None) -> dict:
    if not is_nmcli_available():
        return {"status": "error", "message": "NetworkManager (nmcli) is not installed."}

    devs = get_wifi_devices()
    if not devs:
        return {"status": "error", "message": "No Wi-Fi interface detected on this machine."}

    target_dev = ifname or devs[0]["device"]
    if not ssid or not password:
        def_ssid, def_pass = generate_default_credentials()
        ssid = ssid or def_ssid
        password = password or def_pass

    cmd = ["nmcli", "device", "wifi", "hotspot", "ifname", target_dev, "ssid", ssid, "password", password]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            return {
                "status": "ok",
                "ssid": ssid,
                "password": password,
                "device": target_dev,
                "message": f"Hotspot '{ssid}' started successfully."
            }
        else:
            return {"status": "error", "message": proc.stderr or proc.stdout or "Failed to start hotspot"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def stop_hotspot(ifname: str = None) -> dict:
    if not is_nmcli_available():
        return {"status": "error", "message": "NetworkManager is not available."}

    active = get_active_hotspot()
    if active.get("active"):
        con_name = active.get("name", "Hotspot")
        try:
            proc = subprocess.run(["nmcli", "connection", "down", con_name], capture_output=True, text=True, timeout=10)
            return {"status": "ok", "message": "Hotspot stopped."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    if ifname:
        try:
            subprocess.run(["nmcli", "device", "disconnect", ifname], capture_output=True, text=True, timeout=10)
            return {"status": "ok", "message": f"Disconnected interface {ifname}."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {"status": "ok", "message": "No active hotspot found."}

