import os
import sys
import json
import time
import socket
import urllib.parse
import mimetypes
import subprocess
import zipfile
import tempfile
import shutil
import base64
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import threading
import binascii
import re

from .config import (
    get_web_dir, get_icon_file, get_default_share_dir,
    write_runtime_info, clear_runtime_info
)
from .qr import get_svg_qr, get_terminal_qr, get_wifi_qr_text, generate_qr_matrix
from .devices import (
    DeviceTracker, get_pc_device_name, is_local_ip,
    save_device_name, load_saved_devices
)
from .transfers import TransferTracker, format_size
from .clipboard import (
    get_system_clipboard, set_system_clipboard_text, set_system_clipboard_image
)
from .notifications import (
    notify_device_connected, notify_transfer_completed, notify_clipboard_synced
)
from .hotspot import (
    is_nmcli_available, get_active_hotspot, start_hotspot, stop_hotspot
)
from .auth import AuthManager
from .conflict import resolve_filename_conflict

def get_local_ips():
    ips = []
    # 1. Try socket connection to public DNS
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not is_local_ip(ip):
            ips.append(ip)
    except Exception:
        pass

    # 2. Try parsing hostname / interfaces via hostname -I or ip route
    try:
        out = subprocess.check_output(['hostname', '-I'], text=True, stderr=subprocess.DEVNULL)
        for cand in out.strip().split():
            if cand and not is_local_ip(cand) and cand not in ips:
                ips.append(cand)
    except Exception:
        pass

    # 3. Fallback
    if not ips:
        ips = ['127.0.0.1']
    return ips

def get_disk_stats(path: Path):
    try:
        total_b, used_b, free_b = shutil.disk_usage(path)
        pct_free = (free_b / total_b) * 100 if total_b > 0 else 0
        pct_used = (used_b / total_b) * 100 if total_b > 0 else 0
        return {
            'free_bytes': free_b,
            'total_bytes': total_b,
            'used_bytes': used_b,
            'free_str': format_size(free_b),
            'total_str': format_size(total_b),
            'used_str': format_size(used_b),
            'pct_free': round(pct_free),
            'pct_used': round(pct_used)
        }
    except Exception:
        return {
            'free_bytes': 0, 'total_bytes': 0, 'used_bytes': 0,
            'free_str': 'Available', 'total_str': '', 'used_str': '',
            'pct_free': 100, 'pct_used': 0
        }

class Stats:
    start_time = time.time()
    total_uploads = 0
    total_downloads = 0
    total_uploaded_bytes = 0
    total_downloaded_bytes = 0
    _lock = threading.Lock()

    @classmethod
    def record_upload(cls, size_bytes):
        with cls._lock:
            cls.total_uploads += 1
            cls.total_uploaded_bytes += size_bytes

    @classmethod
    def record_download(cls, size_bytes):
        with cls._lock:
            cls.total_downloads += 1
            cls.total_downloaded_bytes += size_bytes

class BeamTracker:
    beams = []
    dismissed = set()
    _lock = threading.Lock()

    @classmethod
    def add_beam(cls, beam_id, name, rel_path, size, is_dir, sender_name, sender_ip):
        with cls._lock:
            # If beam for this top-level path already exists (e.g. chunked or multi-file folder upload), update size
            for b in cls.beams:
                if b['path'] == rel_path:
                    b['size'] = max(b['size'], size)
                    b['time'] = time.time()
                    return
            if len(cls.beams) >= 30:
                cls.beams.pop(0)
            cls.beams.append({
                'id': beam_id,
                'name': name,
                'path': rel_path,
                'size': size,
                'is_dir': is_dir,
                'sender': sender_name,
                'sender_ip': sender_ip,
                'time': time.time()
            })

    @classmethod
    def get_active_beams(cls, client_ip):
        with cls._lock:
            now = time.time()
            cls.beams = [b for b in cls.beams if now - b['time'] < 600]
            res = []
            for b in cls.beams:
                if b['id'] not in cls.dismissed and (b['id'], client_ip) not in cls.dismissed:
                    if is_local_ip(b['sender_ip']) and not is_local_ip(client_ip):
                        res.append(b)
                    elif b['sender_ip'] != client_ip:
                        res.append(b)
            return res

    @classmethod
    def dismiss_beam(cls, beam_id, client_ip=None):
        with cls._lock:
            cls.dismissed.add(beam_id)
            if client_ip:
                cls.dismissed.add((beam_id, client_ip))

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def server_bind(self):
        super().server_bind()
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass

class HotspotHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    shared_dir = get_default_share_dir()
    server_port = 8080
    primary_ip = "127.0.0.1"

    def setup(self):
        super().setup()
        try:
            self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8 * 1024 * 1024)
            self.connection.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 8 * 1024 * 1024)
        except Exception:
            pass

    def log_message(self, format, *args):
        # Silence default HTTP server console noise
        pass

    def send_json(self, data, status=200):
        try:
            body = json.dumps(data).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, OSError):
            self.close_connection = True

    def resolve_safe_path(self, rel_path):
        try:
            clean_rel = os.path.normpath(urllib.parse.unquote(rel_path or '')).lstrip('/')
            base = self.shared_dir.resolve()
            if clean_rel in ('.', ''):
                return base
            target = (self.shared_dir / clean_rel).resolve()
            if target == base or target.is_relative_to(base):
                return target
        except Exception:
            pass
        return None

    def is_client_local(self):
        client_ip = self.client_address[0]
        return is_local_ip(client_ip) or client_ip == self.primary_ip

    def check_auth(self, query=None):
        if not AuthManager.auth_enabled:
            return True
        if self.is_client_local():
            return True
        auth_header = self.headers.get('Authorization', '')
        token = ''
        if auth_header.startswith('Bearer '):
            token = auth_header[7:].strip()
        if not token:
            token = self.headers.get('X-Auth-Token', '').strip()
        if not token and query:
            token = query.get('token', [''])[0].strip()
        client_ip = self.client_address[0]
        return AuthManager.is_authorized(client_ip, token)

    def read_json_body(self, max_size=50*1024*1024):
        try:
            length = int(self.headers.get('Content-Length', 0))
        except (ValueError, TypeError):
            return None, "Invalid Content-Length"
        if length < 0:
            return None, "Invalid Content-Length"
        if length > max_size:
            return None, "Payload too large"
        if length == 0:
            return {}, None
        try:
            raw = self.rfile.read(length)
            return json.loads(raw.decode('utf-8')), None
        except UnicodeDecodeError:
            return None, "Encoding error: expected UTF-8"
        except json.JSONDecodeError as e:
            return None, f"Malformed JSON: {e}"
        except Exception as e:
            return None, str(e)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        web_dir = get_web_dir()

        if path in ('/', '/index.html'):
            index_path = web_dir / "index.html"
            if index_path.exists():
                content = index_path.read_text(encoding='utf-8')
            else:
                content = "<h1>Hotspot Share</h1><p>Web frontend missing.</p>"

            icon_png = get_icon_file(512, "png")
            icon_b64 = ""
            if icon_png and icon_png.is_file():
                icon_b64 = base64.b64encode(icon_png.read_bytes()).decode('ascii')
            is_auth_required = AuthManager.auth_enabled and not self.is_client_local()
            if is_auth_required and self.check_auth(query):
                is_auth_required = False

            auth_attr = ' data-auth-locked="true"' if is_auth_required else ''
            content = content.replace('__AUTH_LOCKED__', auth_attr)

            body = content.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.send_header('Accept-CH', 'Sec-CH-UA-Model, Sec-CH-UA-Platform, Sec-CH-UA-Platform-Version')
            self.send_header('Permissions-Policy', 'ch-ua-model=*, ch-ua-platform=*')
            self.end_headers()
            self.wfile.write(body)
            return

        elif path == '/style.css':
            css_path = web_dir / "style.css"
            if css_path.exists():
                data = css_path.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'text/css; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
                self.end_headers()
                self.wfile.write(data)
                return

        elif path == '/app.js':
            js_path = web_dir / "app.js"
            if js_path.exists():
                data = js_path.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'application/javascript; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
                self.send_header('Pragma', 'no-cache')
                self.send_header('Expires', '0')
                self.end_headers()
                self.wfile.write(data)
                return

        elif path == '/manifest.json':
            manifest_path = web_dir / "manifest.json"
            if manifest_path.exists():
                data = manifest_path.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'application/manifest+json; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

        elif path == '/sw.js':
            sw_path = web_dir / "sw.js"
            if sw_path.exists():
                data = sw_path.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'application/javascript; charset=utf-8')
                self.send_header('Service-Worker-Allowed', '/')
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return

        elif path in ('/icon.png', '/icon-192.png', '/icon-512.png', '/favicon.ico', '/apple-touch-icon.png'):
            target_icon = web_dir / path.lstrip('/')
            data = None
            if target_icon.exists() and target_icon.is_file():
                data = target_icon.read_bytes()
            else:
                icon_png = get_icon_file(512, "png")
                if icon_png and icon_png.is_file():
                    data = icon_png.read_bytes()
            if data is not None:
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'public, max-age=86400')
                self.end_headers()
                self.wfile.write(data)
                return

        elif path in ('/icon.svg', '/favicon.svg'):
            icon_svg = get_icon_file(512, "svg")
            if icon_svg and icon_svg.is_file():
                data = icon_svg.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'image/svg+xml')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'public, max-age=86400')
                self.end_headers()
                self.wfile.write(data)
                return

        # Status endpoint is public so mobile UI can check if PIN is required
        elif path == '/api/status':
            proto = "https" if getattr(self, 'is_ssl', False) else "http"
            server_url = f"{proto}://{self.primary_ip}:{self.server_port}"
            local_domain = f"{proto}://{socket.gethostname()}.local:{self.server_port}"
            phones = DeviceTracker.get_connected_phones()
            disk = get_disk_stats(self.shared_dir)
            qr_svg = get_svg_qr(server_url)
            qr_matrix = generate_qr_matrix(server_url)
            transfers = TransferTracker.get_transfers_state()
            hotspot_info = get_active_hotspot()

            is_client_authed = self.check_auth(query)

            self.send_json({
                'connected': len(phones) > 0,
                'is_local_client': self.is_client_local(),
                'client_ip': self.client_address[0],
                'pc_name': get_pc_device_name(),
                'pc_disk': disk,
                'phones': phones,
                'transfers': transfers,
                'cancel_all_time': TransferTracker.last_cancel_all_time,
                'server_url': server_url,
                'local_domain': local_domain,
                'is_ssl': getattr(self, 'is_ssl', False),
                'qr_svg': qr_svg,
                'qr_matrix': qr_matrix,
                'auth_required': AuthManager.auth_enabled and not self.is_client_local() and not is_client_authed,
                'auth_enabled': AuthManager.auth_enabled,
                'is_authenticated': is_client_authed,
                'pin_code': AuthManager.pin_code if self.is_client_local() else "",
                'formatted_pin': AuthManager.get_formatted_pin() if self.is_client_local() else "",
                'hotspot_active': hotspot_info.get('active', False),
                'hotspot_name': hotspot_info.get('name', ''),
                'beams': BeamTracker.get_active_beams(self.client_address[0])
            })
            return

        elif path == '/api/dismiss_beam':
            beam_id = query.get('id', [''])[0]
            if beam_id:
                BeamTracker.dismiss_beam(beam_id, self.client_address[0])
            self.send_json({'status': 'ok'})
            return

        # Authenticated endpoints check
        if not self.check_auth(query):
            self.send_json({'status': 'unauthorized', 'error': 'PIN authentication required'}, status=401)
            return

        if path == '/api/files':
            req_dir = query.get('dir', [''])[0]
            target_dir = self.resolve_safe_path(req_dir)
            if not target_dir or not target_dir.is_dir():
                self.send_json([])
                return

            items = []
            for p in sorted(target_dir.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if not p.name.startswith('.'):
                    try:
                        st = p.stat()
                        mtime_str = time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime))
                        rel_to_root = str(p.relative_to(self.shared_dir.resolve()))
                        if p.is_dir():
                            item_count = sum(1 for c in p.iterdir() if not c.name.startswith('.'))
                            items.append({
                                'name': p.name,
                                'path': rel_to_root,
                                'is_dir': True,
                                'item_count': item_count,
                                'mtime': mtime_str
                            })
                        else:
                            items.append({
                                'name': p.name,
                                'path': rel_to_root,
                                'is_dir': False,
                                'size': st.st_size,
                                'mtime': mtime_str
                            })
                    except (OSError, PermissionError):
                        continue
            self.send_json(items)
            return

        elif path == '/api/upload_status':
            transfer_id = query.get('id', [''])[0]
            filename = query.get('name', [''])[0]
            rel_path = query.get('relPath', [''])[0]
            target_dir = query.get('targetDir', [''])[0]

            if rel_path:
                clean_rel = os.path.normpath(urllib.parse.unquote(rel_path)).lstrip('/')
            else:
                clean_rel = os.path.basename(urllib.parse.unquote(filename))

            base = self.shared_dir.resolve()
            if target_dir:
                clean_target_dir = os.path.normpath(urllib.parse.unquote(target_dir)).lstrip('/')
                target_path = (base / clean_target_dir / clean_rel).resolve()
            else:
                target_path = (base / clean_rel).resolve()

            if not (target_path == base or target_path.is_relative_to(base)):
                target_path = base / os.path.basename(clean_rel)

            offset = 0
            if target_path.exists() and not target_path.is_dir() and not TransferTracker.is_cancelled(transfer_id):
                try:
                    offset = target_path.stat().st_size
                except Exception:
                    offset = 0

            self.send_json({'status': 'ok', 'offset': offset})
            return

        elif path == '/api/download':
            req_path = query.get('path', [''])[0]
            target_path = self.resolve_safe_path(req_path)

            if not target_path or not target_path.exists():
                self.send_error(404, "File/Folder Not Found")
                return

            t_stamp = time.strftime('%H:%M:%S')

            if target_path.is_dir():
                folder_name = target_path.name or "HotspotShare"
                temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
                temp_zip_path = Path(temp_zip.name)
                try:
                    with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                        base_resolved = self.shared_dir.resolve()
                        for root, _, files in os.walk(target_path):
                            for file in files:
                                if not file.startswith('.'):
                                    full_file_path = Path(root) / file
                                    # Protect against symlinks escaping shared directory
                                    if full_file_path.is_symlink():
                                        res_link = full_file_path.resolve()
                                        if not (res_link == base_resolved or res_link.is_relative_to(base_resolved)):
                                            continue
                                    arcname = full_file_path.relative_to(target_path)
                                    zf.write(full_file_path, arcname)
                    temp_zip.close()

                    zip_size = temp_zip_path.stat().st_size
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/zip')
                    self.send_header('Content-Disposition', f'attachment; filename="{folder_name}.zip"')
                    self.send_header('Content-Length', str(zip_size))
                    self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
                    self.end_headers()
                    self.wfile.flush()

                    start_t = time.time()
                    with open(temp_zip_path, 'rb', buffering=4*1024*1024) as f:
                        while True:
                            chunk = f.read(1024 * 1024)
                            if not chunk: break
                            self.wfile.write(chunk)
                    
                    elapsed = max(0.001, time.time() - start_t)
                    speed_mb = (zip_size / (1024 * 1024)) / elapsed
                    Stats.record_download(zip_size)
                    print(f" \033[90m{t_stamp}\033[0m  \033[36m[DOWNLOAD]  \033[0m {folder_name}.zip \033[90m({format_size(zip_size)})\033[0m \033[32m{speed_mb:.1f} MB/s\033[0m")
                finally:
                    try:
                        temp_zip.close()
                    except Exception:
                        pass
                    if temp_zip_path.exists():
                        try:
                            temp_zip_path.unlink()
                        except Exception:
                            pass
                return

            file_size = target_path.stat().st_size
            mime_type, _ = mimetypes.guess_type(str(target_path))
            mime_type = mime_type or 'application/octet-stream'

            range_header = self.headers.get('Range')
            if range_header and range_header.startswith('bytes='):
                ranges = range_header[6:].split('-')
                start = int(ranges[0]) if ranges[0] else 0
                end = int(ranges[1]) if ranges[1] else file_size - 1
                if start >= file_size or end >= file_size or start > end:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{file_size}')
                    self.end_headers()
                    return

                length = end - start + 1
                self.send_response(206)
                self.send_header('Content-Type', mime_type)
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                self.send_header('Content-Length', str(length))
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
                self.end_headers()
                self.wfile.flush()

                with open(target_path, 'rb', buffering=4*1024*1024) as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(remaining, 1024 * 1024))
                        if not chunk: break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            else:
                self.send_response(200)
                self.send_header('Content-Type', mime_type)
                self.send_header('Content-Length', str(file_size))
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
                self.end_headers()
                self.wfile.flush()

                start_t = time.time()
                with open(target_path, 'rb', buffering=4*1024*1024) as f:
                    while True:
                        chunk = f.read(1024 * 1024)
                        if not chunk: break
                        self.wfile.write(chunk)

                elapsed = max(0.001, time.time() - start_t)
                speed_mb = (file_size / (1024 * 1024)) / elapsed
                Stats.record_download(file_size)
                print(f" \033[90m{t_stamp}\033[0m  \033[36m[DOWNLOAD]  \033[0m {target_path.name} \033[90m({format_size(file_size)})\033[0m \033[32m{speed_mb:.1f} MB/s\033[0m")
            return

        elif path == '/api/clipboard':
            clip_data = get_system_clipboard()
            self.send_json(clip_data)
            return

        elif path == '/api/open-url':
            url = query.get('url', [''])[0]
            if url and (url.startswith('https://') or url.startswith('http://') or url.startswith('mailto:')):
                try:
                    subprocess.Popen(['xdg-open', url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
            self.send_json({'status': 'ok'})
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        t_stamp = time.strftime('%H:%M:%S')

        # Public auth verify endpoint
        if path == '/api/auth/verify':
            data, err = self.read_json_body(max_size=4096)
            if err:
                self.send_json({'status': 'error', 'message': err}, status=400)
                return
            raw_val = (data.get('pin') or '').strip()
            pin = re.sub(r'[\s\-]+', '', raw_val)
            client_ip = self.client_address[0]
            ok, token_or_reason = AuthManager.verify_pin(pin, client_ip)
            if ok:
                self.send_json({'status': 'ok', 'token': token_or_reason})
            elif token_or_reason == 'rate-limited':
                self.send_json({'status': 'error', 'message': 'Too many failed attempts. Please wait 30 seconds.'}, status=429)
            else:
                self.send_json({'status': 'error', 'message': 'Incorrect PIN code. Please check the code on your PC.'}, status=403)
            return

        elif path == '/api/auth/configure':
            if not self.is_client_local():
                self.send_json({'status': 'error', 'message': 'Security: PIN configuration is restricted to the host PC'}, status=403)
                return
            data, err = self.read_json_body(max_size=4096)
            if err:
                self.send_json({'status': 'error', 'message': err}, status=400)
                return
            action = data.get('action', 'toggle')
            if action == 'enable':
                custom_pin = data.get('pin')
                pin = AuthManager.enable_pin_auth(custom_pin)
                self.send_json({'status': 'ok', 'auth_enabled': True, 'pin_code': pin, 'formatted_pin': AuthManager.get_formatted_pin()})
            elif action == 'disable':
                AuthManager.disable_pin_auth()
                self.send_json({'status': 'ok', 'auth_enabled': False, 'pin_code': '', 'formatted_pin': ''})
            elif action == 'regenerate':
                pin = AuthManager.regenerate_pin()
                self.send_json({'status': 'ok', 'auth_enabled': True, 'pin_code': pin, 'formatted_pin': AuthManager.get_formatted_pin()})
            elif action in ('disconnect', 'revoke'):
                with AuthManager._lock:
                    pin = AuthManager.regenerate_pin()
                with DeviceTracker._lock:
                    DeviceTracker.active_sessions.clear()
                print(f" \033[90m{t_stamp}\033[0m  \033[33m[DISCONNECT]\033[0m All paired devices revoked & disconnected. New PIN: {AuthManager.get_formatted_pin()}")
                self.send_json({'status': 'ok', 'auth_enabled': True, 'pin_code': pin, 'formatted_pin': AuthManager.get_formatted_pin(), 'disconnected': True})
            elif action == 'set_pin':
                new_pin = (data.get('pin') or '').strip().replace(' ', '')
                if len(new_pin) == 8 and new_pin.isdigit():
                    AuthManager.enable_pin_auth(new_pin)
                    self.send_json({'status': 'ok', 'auth_enabled': True, 'pin_code': new_pin, 'formatted_pin': AuthManager.get_formatted_pin()})
                else:
                    self.send_json({'status': 'error', 'message': 'PIN must be exactly 8 digits'}, status=400)
            else:
                self.send_json({'status': 'error', 'message': 'Unknown action'}, status=400)
            return

        elif path == '/api/auth/disconnect':
            client_ip = self.client_address[0]
            auth_header = self.headers.get('Authorization', '')
            token = auth_header[7:].strip() if auth_header.startswith('Bearer ') else self.headers.get('X-Auth-Token', '').strip()

            if self.is_client_local():
                # Disconnect all connected devices and revoke sharing code (generate a new 8-digit PIN)
                new_pin = AuthManager.regenerate_pin()
                with DeviceTracker._lock:
                    DeviceTracker.active_sessions.clear()
                formatted = AuthManager.get_formatted_pin()
                print(f" \033[90m{t_stamp}\033[0m  \033[33m[DISCONNECT]\033[0m All paired sessions terminated. New PIN: {formatted}")
                self.send_json({
                    'status': 'ok',
                    'disconnected': True,
                    'pin_code': new_pin,
                    'formatted_pin': formatted,
                    'message': 'All devices disconnected and PIN revoked. A new 8-digit PIN has been generated.'
                })
            else:
                # Phone unpairs its own session
                AuthManager.revoke_session(client_ip, token)
                with DeviceTracker._lock:
                    DeviceTracker.active_sessions.pop(client_ip, None)
                print(f" \033[90m{t_stamp}\033[0m  \033[33m[UNPAIR]\033[0m Device at {client_ip} revoked pairing session")
                self.send_json({
                    'status': 'ok',
                    'disconnected': True,
                    'unpaired': True,
                    'message': 'Session disconnected and pairing revoked.'
                })
            return

        # Check authentication for remaining endpoints
        if not self.check_auth(query):
            self.send_json({'status': 'unauthorized', 'error': 'PIN authentication required'}, status=401)
            return

        if path == '/api/heartbeat':
            data, err = self.read_json_body(max_size=65536)
            if err:
                self.send_json({'status': 'error', 'message': err}, status=400)
                return
            ua = data.get('ua') or self.headers.get('User-Agent', '')
            model = data.get('model', '')
            nickname = data.get('nickname', '')
            storage = data.get('storage')
            client_ip = self.client_address[0]
            is_new = DeviceTracker.register_heartbeat(client_ip, ua, model, nickname, storage)
            if is_new and not is_local_ip(client_ip):
                dev_name = DeviceTracker.active_sessions.get(client_ip, {}).get('device_name', 'Phone')
                notify_device_connected(dev_name)
            self.send_json({'status': 'ok'})
            return

        elif path == '/api/rename_device':
            data, err = self.read_json_body(max_size=4096)
            if err:
                self.send_json({'status': 'error', 'message': err}, status=400)
                return
            if self.is_client_local():
                target_ip = data.get('ip') or self.client_address[0]
            else:
                target_ip = self.client_address[0]
            new_name = str(data.get('name', '')).strip()
            if new_name:
                save_device_name(target_ip, new_name)
                with DeviceTracker._lock:
                    if target_ip in DeviceTracker.active_sessions:
                        DeviceTracker.active_sessions[target_ip]['device_name'] = new_name
            self.send_json({'status': 'ok'})
            return

        elif path == '/api/cancel_transfer':
            data, _ = self.read_json_body(max_size=4096)
            data = data or {}
            tx_id = data.get('id') or query.get('id', [''])[0]
            if tx_id:
                TransferTracker.cancel_transfer(tx_id)
            else:
                TransferTracker.cancel_all()
            self.send_json({'status': 'ok'})
            return

        elif path == '/api/cancel_all':
            TransferTracker.cancel_all()
            self.send_json({'status': 'ok'})
            return

        elif path == '/api/hotspot/start':
            res = start_hotspot()
            self.send_json(res)
            return

        elif path == '/api/hotspot/stop':
            res = stop_hotspot()
            self.send_json(res)
            return

        elif path == '/api/upload':
            client_ip = self.client_address[0]
            transfer_id = query.get('id', [''])[0]
            filename = query.get('name', ['uploaded_file'])[0]
            rel_path = query.get('relPath', [''])[0]
            target_dir = query.get('targetDir', [''])[0]

            try:
                offset = int(query.get('offset', [self.headers.get('X-Upload-Offset', '0')])[0])
                total_file_size = int(query.get('totalSize', [self.headers.get('X-Total-Size', '0')])[0])
                if offset < 0 or total_file_size < 0:
                    raise ValueError
            except (ValueError, TypeError):
                self.send_json({'status': 'error', 'message': 'Invalid offset or totalSize'}, status=400)
                return

            if rel_path:
                clean_rel = os.path.normpath(urllib.parse.unquote(rel_path)).lstrip('/')
            else:
                clean_rel = os.path.basename(urllib.parse.unquote(filename))

            if not clean_rel or clean_rel in ('.', '..'):
                clean_rel = f"file_{int(time.time()*1000)}"

            if not transfer_id:
                transfer_id = f"tx_{int(time.time()*1000)}_{abs(hash(clean_rel))%10000}"

            base = self.shared_dir.resolve()
            if target_dir:
                clean_target_dir = os.path.normpath(urllib.parse.unquote(target_dir)).lstrip('/')
                target_path = (base / clean_target_dir / clean_rel).resolve()
            else:
                target_path = (base / clean_rel).resolve()

            if not (target_path == base or target_path.is_relative_to(base)):
                target_path = base / os.path.basename(clean_rel)

            if target_path.is_dir():
                target_path = target_path / os.path.basename(clean_rel)

            conflict_mode = query.get('conflict', [self.headers.get('X-Conflict-Mode', 'rename')])[0]
            if offset == 0:
                if conflict_mode == 'skip' and target_path.exists() and total_file_size > 0 and target_path.stat().st_size == total_file_size:
                    self.send_json({'status': 'skipped', 'message': 'File already exists with matching size', 'path': str(target_path.relative_to(base))})
                    return
                target_path = resolve_filename_conflict(target_path, strategy=conflict_mode)
                TransferTracker.set_resolved_path(transfer_id, target_path)
            else:
                cached = TransferTracker.get_resolved_path(transfer_id)
                if cached:
                    target_path = cached

            target_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length < 0:
                    raise ValueError
            except (ValueError, TypeError):
                content_length = 0

            total_size = total_file_size or (offset + content_length)
            display_name = str(target_path.relative_to(base))
            sender_name = DeviceTracker.active_sessions.get(client_ip, {}).get('device_name', "Phone")

            if TransferTracker.is_cancelled(transfer_id):
                self.close_connection = True
                self.send_json({'status': 'cancelled', 'error': 'Transfer cancelled'}, status=400)
                return

            TransferTracker.start_transfer(transfer_id, filename, clean_rel, total_size, client_ip, sender_name, sock=self.connection)
            TransferTracker.update_progress(transfer_id, offset)

            start_t = time.time()
            written = 0
            last_report_t = start_t
            cancelled = False
            error_occurred = False
            error_message = ""

            try:
                # Proper resume: open in r+b, seek to offset and truncate stale data
                if offset > 0 and target_path.exists():
                    out_f = open(target_path, 'r+b')
                    out_f.seek(offset)
                    out_f.truncate()
                else:
                    out_f = open(target_path, 'wb')

                with out_f:
                    remaining = content_length
                    while remaining > 0:
                        if TransferTracker.is_cancelled(transfer_id):
                            cancelled = True
                            break

                        chunk = self.rfile.read(min(remaining, 1024 * 1024))
                        if not chunk:
                            if remaining > 0:
                                error_occurred = True
                                error_message = "Upload disconnected before completion"
                            break

                        out_f.write(chunk)
                        written += len(chunk)
                        remaining -= len(chunk)

                        now_t = time.time()
                        if now_t - last_report_t > 0.08:
                            TransferTracker.update_progress(transfer_id, offset + written)
                            last_report_t = now_t

                        if TransferTracker.is_cancelled(transfer_id):
                            cancelled = True
                            break

                if cancelled or TransferTracker.is_cancelled(transfer_id):
                    if target_path.exists():
                        try:
                            target_path.unlink()
                        except Exception:
                            pass
                    TransferTracker.finish_transfer(transfer_id, success=False, error_msg="Cancelled", is_cancelled=True)
                    t_stamp = time.strftime('%H:%M:%S')
                    print(f" \033[90m{t_stamp}\033[0m  \033[33m[CANCEL]    \033[0m {display_name}")
                    self.close_connection = True
                    self.send_json({'status': 'cancelled', 'error': 'Cancelled'}, status=400)
                    return

                if error_occurred or (offset + written < total_size):
                    TransferTracker.update_progress(transfer_id, offset + written)
                    t_stamp = time.strftime('%H:%M:%S')
                    print(f" \033[90m{t_stamp}\033[0m  \033[33m[PAUSED]    \033[0m {display_name} ({format_size(offset + written)}/{format_size(total_size)}) - preserved for resume")
                    self.close_connection = True
                    self.send_json({'status': 'paused', 'received': offset + written, 'error': error_message or 'Incomplete chunk'}, status=400)
                    return

                TransferTracker.update_progress(transfer_id, offset + written)
                TransferTracker.finish_transfer(transfer_id, success=True)
                notify_transfer_completed(target_path.name, format_size(total_size))
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                is_canc = TransferTracker.is_cancelled(transfer_id)
                if is_canc and target_path.exists():
                    try:
                        target_path.unlink()
                    except Exception:
                        pass
                TransferTracker.finish_transfer(transfer_id, success=False, error_msg="Client disconnected", is_cancelled=is_canc)
                self.close_connection = True
                t_stamp = time.strftime('%H:%M:%S')
                if is_canc:
                    print(f" \033[90m{t_stamp}\033[0m  \033[33m[CANCEL]    \033[0m {display_name}")
                else:
                    print(f" \033[90m{t_stamp}\033[0m  \033[33m[PAUSED]    \033[0m {display_name} (Client disconnected - preserved for resume)")
                return
            except Exception as e:
                is_canc = TransferTracker.is_cancelled(transfer_id)
                if is_canc and target_path.exists():
                    try:
                        target_path.unlink()
                    except Exception:
                        pass
                TransferTracker.finish_transfer(transfer_id, success=False, error_msg=str(e), is_cancelled=is_canc)
                self.close_connection = True
                t_stamp = time.strftime('%H:%M:%S')
                if is_canc:
                    print(f" \033[90m{t_stamp}\033[0m  \033[33m[CANCEL]    \033[0m {display_name}")
                    self.send_json({'status': 'cancelled', 'error': 'Cancelled'}, status=400)
                else:
                    print(f" \033[90m{t_stamp}\033[0m  \033[31m[ERROR]     \033[0m {display_name}: {e}")
                    try:
                        self.send_error(500, f"Upload error: {e}")
                    except Exception:
                        pass
                return

            elapsed = max(0.001, time.time() - start_t)
            speed_mb = ((offset + written) / (1024 * 1024)) / elapsed
            Stats.record_upload(written)

            t_stamp = time.strftime('%H:%M:%S')
            print(f" \033[90m{t_stamp}\033[0m  \033[32m[UPLOAD]    \033[0m {display_name} \033[90m({format_size(offset + written)})\033[0m \033[1;37m{speed_mb:.1f} MB/s\033[0m")

            rel_path_to_base = str(target_path.relative_to(base))
            top_level = clean_target_dir.split('/')[0] if target_dir else (clean_rel.split('/')[0] if '/' in clean_rel else '')
            is_folder = bool(top_level)
            beam_name = top_level if is_folder else os.path.basename(clean_rel)
            beam_path = top_level if is_folder else rel_path_to_base

            BeamTracker.add_beam(
                beam_id=transfer_id,
                name=beam_name,
                rel_path=beam_path,
                size=offset + written,
                is_dir=is_folder,
                sender_name=sender_name,
                sender_ip=client_ip
            )

            self.send_json({'status': 'ok', 'filename': display_name, 'size': offset + written, 'path': rel_path_to_base})
            return

        elif path == '/api/mkdir':
            req_dir = query.get('dir', [''])[0]
            raw_name = urllib.parse.unquote(query.get('name', [''])[0]).strip()
            new_folder_name = os.path.basename(raw_name)
            base_dir = self.resolve_safe_path(req_dir)
            base = self.shared_dir.resolve()
            if base_dir and new_folder_name and new_folder_name not in ('.', '..') and '/' not in raw_name and '\\' not in raw_name:
                new_folder_path = (base_dir / new_folder_name).resolve()
                if new_folder_path == base or new_folder_path.is_relative_to(base):
                    new_folder_path.mkdir(parents=True, exist_ok=True)
                    print(f" \033[90m{t_stamp}\033[0m  \033[34m[MKDIR]     \033[0m {new_folder_path.relative_to(base)}")
                    self.send_json({'status': 'ok'})
                    return
            self.send_error(400, "Invalid directory name")
            return

        elif path == '/api/delete':
            # Security Hardening: Remote deletion is blocked by default to prevent untrusted peers from wiping data
            if not self.is_client_local() and os.environ.get("HOTSPOT_ALLOW_REMOTE_DELETE", "0") != "1":
                self.send_json({'status': 'error', 'message': 'Remote file deletion is disabled by security policy. Only the host PC can delete files.'}, status=403)
                return

            req_path = query.get('path', [''])[0]
            target = self.resolve_safe_path(req_path)
            base = self.shared_dir.resolve()
            if target and target.exists() and target != base:
                display_name = str(target.relative_to(base))
                if target.is_symlink():
                    target.unlink()
                elif target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
                print(f" \033[90m{t_stamp}\033[0m  \033[31m[DELETE]    \033[0m {display_name}")
                self.send_json({'status': 'ok'})
            else:
                self.send_error(404, "Item not found")
            return

        elif path == '/api/clear_all_files':
            if not self.is_client_local() and os.environ.get("HOTSPOT_ALLOW_REMOTE_DELETE", "0") != "1":
                self.send_json({'status': 'error', 'message': 'Remote file deletion is disabled by security policy.'}, status=403)
                return
            base = self.shared_dir.resolve()
            if base.is_dir():
                for item in list(base.iterdir()):
                    try:
                        if item.is_symlink() or item.is_file():
                            item.unlink()
                        elif item.is_dir():
                            shutil.rmtree(item)
                    except Exception:
                        pass
                print(f" \033[90m{t_stamp}\033[0m  \033[31m[CLEAR]     \033[0m All shared files cleared")
            self.send_json({'status': 'ok', 'message': 'All shared files cleared'})
            return

        elif path == '/api/clipboard':
            data, err = self.read_json_body(max_size=25*1024*1024)
            if err:
                self.send_json({'status': 'error', 'message': err}, status=400)
                return
            
            data_type = data.get('type', 'text')
            if data_type == 'image':
                raw_b64 = data.get('data', '')
                if ',' in raw_b64:
                    raw_b64 = raw_b64.split(',', 1)[1]
                try:
                    img_bytes = base64.b64decode(raw_b64)
                except (binascii.Error, ValueError):
                    self.send_json({'status': 'error', 'message': 'Invalid base64 image data'}, status=400)
                    return
                mime = data.get('mime', 'image/png')
                success = set_system_clipboard_image(img_bytes, mime)
                print(f" \033[90m{t_stamp}\033[0m  \033[33m[CLIPBOARD] \033[0m Synced image ({format_size(len(img_bytes))}) to PC (Ctrl+V ready)")
                notify_clipboard_synced(f"Image received ({format_size(len(img_bytes))})")
                self.send_json({'status': 'ok', 'clipboard_synced': success})
            else:
                new_text = str(data.get('text', ''))
                if len(new_text) > 1024 * 1024:
                    self.send_json({'status': 'error', 'message': 'Text payload too large (max 1MB)'}, status=400)
                    return
                success = set_system_clipboard_text(new_text)
                preview = (new_text[:40] + "...") if len(new_text) > 40 else new_text
                print(f" \033[90m{t_stamp}\033[0m  \033[33m[CLIPBOARD] \033[0m Synced text ({len(new_text)} chars) to PC (Ctrl+V ready)")
                notify_clipboard_synced(f"Text received: {preview}")
                self.send_json({'status': 'ok', 'clipboard_synced': success})
            return

        self.send_error(404, "Not Found")
