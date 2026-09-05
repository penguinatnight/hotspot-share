import socket
import json
import time
import threading
import logging
import uuid
from typing import Optional
from . import __version__

DISCOVERY_PORT = 53535
MAGIC_HEADER = "HOTSPOT_SHARE_DISCOVERY"

class DiscoveryBeacon:
    """
    Lightweight, zero-dependency local network peer discovery beacon and responder.
    Broadcasts availability over UDP and answers peer discovery probes.
    """
    def __init__(self, server_url: str, pc_name: str, pin_required: bool = False, port: int = DISCOVERY_PORT):
        self.server_url = server_url
        self.pc_name = pc_name
        self.pin_required = pin_required
        self.port = port
        self.instance_id = uuid.uuid4().hex
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None

    def _get_payload(self) -> bytes:
        info = {
            "magic": MAGIC_HEADER,
            "app": "hotspot-share",
            "version": __version__,
            "name": self.pc_name,
            "url": self.server_url,
            "pin_required": self.pin_required,
            "instance_id": self.instance_id,
            "timestamp": time.time()
        }
        return json.dumps(info).encode("utf-8")

    def _run(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except (AttributeError, OSError):
                pass
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(1.0)
            sock.bind(("", self.port))
            self._sock = sock
        except Exception as e:
            logging.debug("Discovery service socket bind skipped: %s", e)
            return

        payload = self._get_payload()
        last_broadcast = 0.0
        last_response_time = 0.0

        while self.running:
            now = time.time()
            # Broadcast announcement beacon every 5 seconds
            if now - last_broadcast > 5.0:
                try:
                    sock.sendto(payload, ("<broadcast>", self.port))
                    last_broadcast = now
                except Exception:
                    pass

            # Listen for discovery requests / pings
            try:
                data, addr = sock.recvfrom(2048)
                if data:
                    try:
                        req = json.loads(data.decode("utf-8"))
                        # Ignore self-broadcasts and looped-back packets from this instance
                        if req.get("instance_id") == self.instance_id or req.get("url") == self.server_url:
                            continue
                        # CRITICAL FIX: Only reply to active search queries ("ping" or "discover").
                        # Never reply to passive announcement beacons or responses (which contain
                        # MAGIC_HEADER). Replying to announcements creates an explosive UDP packet storm.
                        if req.get("cmd") in ("ping", "discover"):
                            if now - last_response_time >= 0.05:
                                sock.sendto(payload, addr)
                                last_response_time = now
                    except Exception:
                        pass
            except socket.timeout:
                continue
            except Exception:
                if self.running:
                    time.sleep(0.5)

        try:
            sock.close()
        except Exception:
            pass

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run, name="HotspotDiscovery", daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

_active_beacon: Optional[DiscoveryBeacon] = None
_beacon_lock = threading.Lock()

def start_discovery_beacon(server_url: str, pc_name: str, pin_required: bool = False, port: int = DISCOVERY_PORT) -> DiscoveryBeacon:
    global _active_beacon
    with _beacon_lock:
        if _active_beacon:
            _active_beacon.stop()
        _active_beacon = DiscoveryBeacon(server_url, pc_name, pin_required, port)
        _active_beacon.start()
        return _active_beacon

def stop_discovery_beacon():
    global _active_beacon
    with _beacon_lock:
        if _active_beacon:
            _active_beacon.stop()
            _active_beacon = None
