import time
import threading

def format_size(bytes_val):
    if bytes_val is None: return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(bytes_val) < 1024.0:
            return f"{bytes_val:.1f} {unit}" if unit != 'B' else f"{bytes_val} B"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} PB"

class TransferTracker:
    transfers = {}
    transfer_sockets = {}
    cancelled_transfers = {}
    last_cancel_all_time = 0
    _lock = threading.Lock()

    @classmethod
    def start_transfer(cls, transfer_id, filename, rel_path, total_bytes, client_ip, device_name, sock=None):
        with cls._lock:
            now = time.time()
            if transfer_id in cls.cancelled_transfers or now < cls.last_cancel_all_time:
                return

            cls.transfers[transfer_id] = {
                'id': transfer_id,
                'name': filename,
                'rel_path': rel_path,
                'total_bytes': total_bytes,
                'transferred_bytes': 0,
                'start_time': now,
                'last_update': now,
                'speed_mb': 0.0,
                'speed_str': '0 MB/s',
                'status': 'transferring',
                'sender': device_name,
                'client_ip': client_ip,
                'error': '',
                'progress_pct': 0
            }
            if sock:
                cls.transfer_sockets[transfer_id] = sock

    @classmethod
    def update_progress(cls, transfer_id, transferred_bytes):
        with cls._lock:
            tx = cls.transfers.get(transfer_id)
            if not tx or tx['status'] != 'transferring':
                return

            now = time.time()
            elapsed = max(0.001, now - tx['start_time'])
            speed_bps = transferred_bytes / elapsed
            speed_mb = speed_bps / (1024 * 1024)

            tx['transferred_bytes'] = transferred_bytes
            tx['last_update'] = now
            tx['speed_mb'] = round(speed_mb, 1)
            tx['speed_str'] = f"{speed_mb:.1f} MB/s"

            if tx['total_bytes'] > 0:
                tx['progress_pct'] = min(100, int((transferred_bytes / tx['total_bytes']) * 100))

    @classmethod
    def cancel_transfer(cls, transfer_id):
        with cls._lock:
            cls.cancelled_transfers[transfer_id] = time.time()
            tx = cls.transfers.get(transfer_id)
            if tx:
                tx['status'] = 'cancelled'
                tx['speed_mb'] = 0.0
                tx['speed_str'] = 'Cancelled'

            sock = cls.transfer_sockets.pop(transfer_id, None)
            if sock:
                try:
                    sock.shutdown(2)
                    sock.close()
                except Exception:
                    pass

    @classmethod
    def cancel_all(cls):
        with cls._lock:
            cls.last_cancel_all_time = time.time()
            for tx_id, tx in list(cls.transfers.items()):
                if tx['status'] == 'transferring':
                    tx['status'] = 'cancelled'
                    cls.cancelled_transfers[tx_id] = time.time()

            for tx_id, sock in list(cls.transfer_sockets.items()):
                try:
                    sock.shutdown(2)
                    sock.close()
                except Exception:
                    pass
            cls.transfer_sockets.clear()

    @classmethod
    def is_cancelled(cls, transfer_id):
        with cls._lock:
            if transfer_id in cls.cancelled_transfers:
                return True
            tx = cls.transfers.get(transfer_id)
            if tx and tx.get('status') == 'cancelled':
                return True
            if tx and tx.get('start_time', 0) < cls.last_cancel_all_time:
                return True
            return False

    @classmethod
    def finish_transfer(cls, transfer_id, success=True, error_msg="", is_cancelled=False):
        with cls._lock:
            cls.transfer_sockets.pop(transfer_id, None)
            tx = cls.transfers.get(transfer_id)
            if not tx:
                return

            if is_cancelled or transfer_id in cls.cancelled_transfers:
                tx['status'] = 'cancelled'
                tx['speed_str'] = 'Cancelled'
            elif success:
                tx['status'] = 'completed'
                tx['progress_pct'] = 100
                tx['transferred_bytes'] = tx['total_bytes']
                now = time.time()
                elapsed = max(0.001, now - tx['start_time'])
                avg_speed = (tx['total_bytes'] / (1024 * 1024)) / elapsed
                tx['speed_str'] = f"Completed ({avg_speed:.1f} MB/s avg)"
            else:
                tx['status'] = 'error'
                tx['error'] = error_msg
                tx['speed_str'] = 'Failed'

    @classmethod
    def get_transfers_state(cls):
        with cls._lock:
            now = time.time()
            # Clean up old finished transfers after 45s
            for tx_id, tx in list(cls.transfers.items()):
                if tx['status'] in ('completed', 'cancelled', 'error'):
                    if now - tx.get('last_update', now) > 45:
                        cls.transfers.pop(tx_id, None)
                        cls.cancelled_transfers.pop(tx_id, None)

            # Also prune cancelled transfers older than 5 minutes
            for cid, ctime in list(cls.cancelled_transfers.items()):
                if now - ctime > 300:
                    cls.cancelled_transfers.pop(cid, None)

            def sanitize(d):
                return {k: v for k, v in d.items() if isinstance(v, (int, float, str, bool, list, dict))}

            return [sanitize(v) for v in cls.transfers.values()]
