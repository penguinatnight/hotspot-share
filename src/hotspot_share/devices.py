import os
import json
import time
import socket
import re
from pathlib import Path
from .config import get_config_dir

MODEL_MAP = {
    # Samsung Galaxy S-Series
    'SM-S938': 'Samsung Galaxy S25 Ultra', 'SM-S936': 'Samsung Galaxy S25+', 'SM-S931': 'Samsung Galaxy S25',
    'SM-S928': 'Samsung Galaxy S24 Ultra', 'SM-S926': 'Samsung Galaxy S24+', 'SM-S921': 'Samsung Galaxy S24',
    'SM-S918': 'Samsung Galaxy S23 Ultra', 'SM-S916': 'Samsung Galaxy S23+', 'SM-S911': 'Samsung Galaxy S23',
    'SM-S908': 'Samsung Galaxy S22 Ultra', 'SM-S906': 'Samsung Galaxy S22+', 'SM-S901': 'Samsung Galaxy S22',
    'SM-G998': 'Samsung Galaxy S21 Ultra', 'SM-G996': 'Samsung Galaxy S21+', 'SM-G991': 'Samsung Galaxy S21',
    'SM-G990': 'Samsung Galaxy S21 FE', 'SM-S711': 'Samsung Galaxy S23 FE', 'SM-S721': 'Samsung Galaxy S24 FE',
    'SM-G988': 'Samsung Galaxy S20 Ultra', 'SM-G986': 'Samsung Galaxy S20+', 'SM-G981': 'Samsung Galaxy S20', 'SM-G781': 'Samsung Galaxy S20 FE',
    'SM-G975': 'Samsung Galaxy S10+', 'SM-G973': 'Samsung Galaxy S10', 'SM-G970': 'Samsung Galaxy S10e',

    # Samsung Galaxy A-Series
    'SM-A566': 'Samsung Galaxy A56 5G', 'SM-A556': 'Samsung Galaxy A55 5G',
    'SM-A546': 'Samsung Galaxy A54 5G', 'SM-A54': 'Samsung Galaxy A54 5G', 'A546': 'Samsung Galaxy A54 5G',
    'SM-A536': 'Samsung Galaxy A53 5G', 'SM-A528': 'Samsung Galaxy A52s 5G', 'SM-A525': 'Samsung Galaxy A52', 'SM-A526': 'Samsung Galaxy A52 5G',
    'SM-A515': 'Samsung Galaxy A51', 'SM-A516': 'Samsung Galaxy A51 5G',
    'SM-A356': 'Samsung Galaxy A35 5G', 'SM-A346': 'Samsung Galaxy A34 5G', 'SM-A336': 'Samsung Galaxy A33 5G',
    'SM-A256': 'Samsung Galaxy A25 5G', 'SM-A245': 'Samsung Galaxy A24', 'SM-A236': 'Samsung Galaxy A23 5G',
    'SM-A166': 'Samsung Galaxy A16 5G', 'SM-A156': 'Samsung Galaxy A15 5G', 'SM-A155': 'Samsung Galaxy A15',
    'SM-A146': 'Samsung Galaxy A14 5G', 'SM-A145': 'Samsung Galaxy A14',
    'SM-A057': 'Samsung Galaxy A05s', 'SM-A055': 'Samsung Galaxy A05',
    'SM-A736': 'Samsung Galaxy A73 5G', 'SM-A725': 'Samsung Galaxy A72',

    # Samsung Galaxy Note & Z Series
    'SM-N986': 'Samsung Galaxy Note 20 Ultra', 'SM-N981': 'Samsung Galaxy Note 20', 'SM-N975': 'Samsung Galaxy Note 10+', 'SM-N970': 'Samsung Galaxy Note 10',
    'SM-F956': 'Samsung Galaxy Z Fold 6', 'SM-F741': 'Samsung Galaxy Z Flip 6',
    'SM-F946': 'Samsung Galaxy Z Fold 5', 'SM-F731': 'Samsung Galaxy Z Flip 5',
    'SM-F936': 'Samsung Galaxy Z Fold 4', 'SM-F721': 'Samsung Galaxy Z Flip 4',
    'SM-F926': 'Samsung Galaxy Z Fold 3', 'SM-F711': 'Samsung Galaxy Z Flip 3',

    # Google Pixel
    'Pixel 9 Pro XL': 'Google Pixel 9 Pro XL', 'Pixel 9 Pro Fold': 'Google Pixel 9 Pro Fold', 'Pixel 9 Pro': 'Google Pixel 9 Pro', 'Pixel 9': 'Google Pixel 9',
    'Pixel 8a': 'Google Pixel 8a', 'Pixel 8 Pro': 'Google Pixel 8 Pro', 'Pixel 8': 'Google Pixel 8',
    'Pixel 7a': 'Google Pixel 7a', 'Pixel 7 Pro': 'Google Pixel 7 Pro', 'Pixel 7': 'Google Pixel 7',
    'Pixel 6a': 'Google Pixel 6a', 'Pixel 6 Pro': 'Google Pixel 6 Pro', 'Pixel 6': 'Google Pixel 6',
    'Pixel 5': 'Google Pixel 5', 'Pixel 4a': 'Google Pixel 4a',

    # OnePlus
    'CPH2581': 'OnePlus 12', 'CPH2583': 'OnePlus 12', 'CPH2609': 'OnePlus 12R',
    'CPH2449': 'OnePlus 11', 'CPH2451': 'OnePlus 11', 'CPH2413': 'OnePlus 11R',
    'NE2213': 'OnePlus 10 Pro', 'CPH2415': 'OnePlus 10T',
    'LE2123': 'OnePlus 9 Pro', 'LE2113': 'OnePlus 9', 'KB2003': 'OnePlus 8T',

    # Xiaomi / Poco / Redmi
    '2311DRK48G': 'POCO X6 Pro', '23113RKC6G': 'POCO F6 Pro', '24069PC21G': 'POCO F6',
    '23049PCD8G': 'POCO F5', '23013PC75G': 'POCO X5 Pro 5G', 'M2012K11AG': 'POCO F3', 'M2102J20SG': 'POCO X3 Pro',
    '24053PY09C': 'Xiaomi 14 Ultra', '23127PN0CG': 'Xiaomi 14',
    '23078PND5G': 'Xiaomi 13T Pro', '2210132G': 'Xiaomi 13 Pro', '2211133G': 'Xiaomi 13', '2201123G': 'Xiaomi 12 Pro',
    '23090RA98G': 'Redmi Note 13 Pro+', '2312DRA50G': 'Redmi Note 13 Pro', '23129RAA4G': 'Redmi Note 13',
    '22101316G': 'Redmi Note 12 Pro', '2201116SG': 'Redmi Note 11 Pro', '2201117TY': 'Redmi Note 11',

    # Nothing Phone
    'A142': 'Nothing Phone (2a)', 'A065': 'Nothing Phone (2)', 'A063': 'Nothing Phone (1)',

    # Sony
    'XQ-DQ54': 'Sony Xperia 1 V', 'XQ-EC54': 'Sony Xperia 1 VI', 'XQ-DE54': 'Sony Xperia 5 V'
}

def get_device_config_file() -> Path:
    return get_config_dir() / "devices.json"

def load_saved_devices():
    cfg = get_device_config_file()
    if cfg.exists():
        try:
            return json.loads(cfg.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}

def save_device_name(key, name):
    try:
        cfg = get_device_config_file()
        data = load_saved_devices()
        if name and name.strip():
            data[key] = name.strip()
        else:
            data.pop(key, None)
        cfg.write_text(json.dumps(data, indent=2), encoding='utf-8')
    except Exception:
        pass

def save_device_storage(key, storage_data):
    try:
        cfg = get_device_config_file()
        data = load_saved_devices()
        data[f"storage_{key}"] = storage_data
        cfg.write_text(json.dumps(data, indent=2), encoding='utf-8')
    except Exception:
        pass

def get_pc_device_name():
    saved = load_saved_devices().get('__pc_name__')
    if saved:
        return saved
    try:
        if Path("/etc/machine-info").exists():
            for line in Path("/etc/machine-info").read_text().splitlines():
                if line.startswith("PRETTY_HOSTNAME="):
                    val = line.split("=", 1)[1].strip('"\'')
                    if val: return val
    except Exception:
        pass
    host = socket.gethostname()
    user = os.environ.get("USER", "").strip()
    if user and user.lower() not in host.lower():
        return f"{user.capitalize()}'s PC ({host})"
    return f"{host} (PC)"

def is_local_ip(ip):
    if not ip: return True
    return ip in ('127.0.0.1', '::1', 'localhost')

def resolve_device_name(model, ua, nickname='', client_ip=''):
    saved = load_saved_devices()
    if client_ip and client_ip in saved and saved[client_ip]:
        return saved[client_ip]

    if nickname and nickname.strip():
        if client_ip: save_device_name(client_ip, nickname.strip())
        return nickname.strip()

    if model and model.strip():
        m = model.strip()
        for k, v in MODEL_MAP.items():
            if k.lower() in m.lower():
                return v
        if not any(x in m.lower() for x in ('sm-', 'cph', '23', '22', '24', 'pixel', 'iphone')):
            return m

    if 'iPhone' in ua:
        if 'iPhone16' in ua or 'iPhone17' in ua: return 'iPhone 16 Pro'
        if 'iPhone15' in ua: return 'iPhone 15 Pro'
        if 'iPhone14' in ua: return 'iPhone 14'
        return 'Apple iPhone'
    if 'iPad' in ua: return 'Apple iPad'

    for k, v in MODEL_MAP.items():
        if k in ua: return v

    m_match = re.search(r'\(([^)]+)\)', ua)
    if m_match:
        parts = m_match.group(1).split(';')
        for p in parts:
            p = p.strip()
            if 'Build/' in p:
                cand = p.split('Build/')[0].strip()
                for k, v in MODEL_MAP.items():
                    if k in cand: return v
                if len(cand) > 2 and not cand.startswith('Linux') and not cand.startswith('U'):
                    return cand

    if 'Android' in ua: return 'Android Phone'
    if 'Macintosh' in ua: return 'MacBook'
    if 'Windows' in ua: return 'Windows PC'
    if 'Linux' in ua: return 'Linux Client'
    return 'Mobile Device'

class DeviceTracker:
    active_sessions = {}

    @classmethod
    def register_heartbeat(cls, client_ip, ua, model='', nickname='', storage=None):
        now = time.time()
        cls.clean_stale_sessions()

        dev_name = resolve_device_name(model, ua, nickname, client_ip)
        is_new = client_ip not in cls.active_sessions

        cls.active_sessions[client_ip] = {
            'last_seen': now,
            'device_name': dev_name,
            'ip': client_ip,
            'ua': ua,
            'model': model,
            'nickname': nickname or (load_saved_devices().get(client_ip, '')),
            'storage': storage or (load_saved_devices().get(f"storage_{client_ip}")),
            'is_phone': any(x in ua.lower() or x in model.lower() for x in ('android', 'iphone', 'mobile', 'sm-', 'cph', 'pixel'))
        }

        if storage:
            save_device_storage(client_ip, storage)

        return is_new

    @classmethod
    def clean_stale_sessions(cls):
        now = time.time()
        timeout = 16.0
        stale = [ip for ip, sess in cls.active_sessions.items() if now - sess['last_seen'] > timeout]
        for ip in stale:
            cls.active_sessions.pop(ip, None)

    @classmethod
    def get_connected_phones(cls):
        cls.clean_stale_sessions()
        return [sess for ip, sess in cls.active_sessions.items() if not is_local_ip(ip)]

    @classmethod
    def is_phone_connected(cls):
        return len(cls.get_connected_phones()) > 0
