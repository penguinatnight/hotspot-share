import os
import sys
import argparse
import signal
from pathlib import Path

from . import __version__
from .config import (
    get_default_share_dir, write_runtime_info, clear_runtime_info
)
from .qr import get_terminal_qr
from .transfers import TransferTracker, format_size
from .devices import get_pc_device_name
from .hotspot import start_hotspot, get_active_hotspot
from .auth import AuthManager
from .server import (
    ThreadedHTTPServer, HotspotHandler, get_local_ips, get_disk_stats, Stats
)

def main():
    default_dir = str(get_default_share_dir())
    parser = argparse.ArgumentParser(
        prog="hotspot-share",
        description="Hotspot Share - High-Speed Local Wi-Fi File Sharing & Clipboard Sync"
    )
    parser.add_argument('-p', '--port', type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.add_argument('-d', '--dir', type=str, default=default_dir, help=f"Directory for shared files (default: {default_dir})")
    parser.add_argument('--no-qr', action='store_true', help="Do not display QR code in terminal")
    parser.add_argument('--auth', action='store_true', help="Enable 4-digit PIN pairing authentication")
    parser.add_argument('--pin', type=str, default="", help="Set custom 4-digit PIN for pairing")
    parser.add_argument('--hotspot', nargs='?', const='__auto__', help="Automatically launch Wi-Fi Hotspot with optional SSID")
    parser.add_argument('--no-gui', action='store_true', help="Run in headless terminal daemon mode")
    parser.add_argument('-v', '--version', action='version', version=f"%(prog)s {__version__}")

    args = parser.parse_args()

    shared_path = Path(args.dir).expanduser().resolve()
    shared_path.mkdir(parents=True, exist_ok=True)
    HotspotHandler.shared_dir = shared_path

    if args.auth or args.pin:
        pin = AuthManager.enable_pin_auth(args.pin)
    else:
        pin = ""

    if args.hotspot:
        ssid = None if args.hotspot == '__auto__' else args.hotspot
        print("Starting Wi-Fi Hotspot...")
        h_res = start_hotspot(ssid=ssid)
        if h_res.get("status") == "ok":
            print(f"Hotspot active: {h_res.get('ssid')} (Password: {h_res.get('password')})")
        else:
            print(f"Hotspot warning: {h_res.get('message')}")

    port = args.port
    server = None
    for attempt_port in range(port, port + 20):
        try:
            server = ThreadedHTTPServer(('0.0.0.0', attempt_port), HotspotHandler)
            port = attempt_port
            break
        except OSError:
            continue

    if not server:
        print(f"Error: Could not bind to port {args.port} or subsequent ports.")
        sys.exit(1)

    ips = get_local_ips()
    primary_ip = ips[0]
    HotspotHandler.primary_ip = primary_ip
    HotspotHandler.server_port = port
    phone_url = f"http://{primary_ip}:{port}"

    write_runtime_info(port=port, primary_ip=primary_ip, url=phone_url, token=pin, pid=os.getpid())

    def cleanup(signum=None, frame=None):
        clear_runtime_info()
        try:
            server.server_close()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    disk_info = get_disk_stats(shared_path)
    disk_str = f"{disk_info['free_str']} free / {disk_info['total_str']} total ({disk_info['pct_free']}% free)"

    W = 68
    print("\n\033[1;37m┌" + "─" * W + "┐\033[0m")
    print(f"\033[1;37m│\033[0m  \033[1;37mHOTSPOT SHARE v{__version__}\033[0m" + " " * (W - 24 - len(__version__)) + "\033[32;1m[RUNNING]\033[0m  \033[1;37m│\033[0m")
    print("\033[1;37m├" + "─" * W + "┤\033[0m")
    print(f"\033[1;37m│\033[0m  \033[1mWeb Interface\033[0m : \033[1;36m{phone_url:<50}\033[0m \033[1;37m│\033[0m")
    print(f"\033[1;37m│\033[0m  \033[1mSave Location\033[0m : \033[33m{str(shared_path):<50}\033[0m \033[1;37m│\033[0m")
    print(f"\033[1;37m│\033[0m  \033[1mDisk Space\033[0m    : \033[37m{disk_str:<50}\033[0m \033[1;37m│\033[0m")
    print(f"\033[1;37m│\033[0m  \033[1mLocal IP\033[0m      : \033[37m{primary_ip} (Port {port}){'':<33}\033[0m \033[1;37m│\033[0m")
    if pin:
        print(f"\033[1;37m│\033[0m  \033[1;33mPairing PIN\033[0m   : \033[1;32m{pin:<50}\033[0m \033[1;37m│\033[0m")
    print("\033[1;37m├" + "─" * W + "┤\033[0m")
    
    if not args.no_qr:
        print("\033[1;37m│\033[0m  \033[90mScan QR code with mobile camera to connect:\033[0m" + " " * (W - 47) + "\033[1;37m│\033[0m")
        print("\033[1;37m│\033[0m" + " " * W + "\033[1;37m│\033[0m")
        qr_lines = get_terminal_qr(phone_url, indent=16).split('\n')
        for ql in qr_lines:
            padded = ql.ljust(W)
            print(f"\033[1;37m│\033[0m{padded}\033[1;37m│\033[0m")
        print("\033[1;37m│\033[0m" + " " * W + "\033[1;37m│\033[0m")
        print("\033[1;37m├" + "─" * W + "┤\033[0m")

    print(f"\033[1;37m│\033[0m  \033[1;37mACTIVITY LOG\033[0m" + " " * (W - 34) + "\033[90m[Press Ctrl+C to stop]\033[0m  \033[1;37m│\033[0m")
    print("\033[1;37m└" + "─" * W + "┘\033[0m\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        cleanup()

if __name__ == '__main__':
    main()
