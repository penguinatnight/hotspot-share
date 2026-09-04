import secrets
import string
import time
import threading

class AuthManager:
    DEFAULT_PIN_LENGTH = 8
    TOKEN_TTL = 86400       # 24 hours
    MAX_FAILURES = 5
    FAIL_WINDOW = 60        # 1 minute window
    LOCKOUT_TIME = 30       # 30 seconds lockout

    auth_enabled = True
    pin_code = "".join(secrets.choice(string.digits) for _ in range(DEFAULT_PIN_LENGTH))
    authorized_tokens = {}  # token -> {'ip': ip, 'created': timestamp}
    authorized_ips = {}     # ip -> timestamp of authorization
    failed_attempts = {}    # ip -> list of failure timestamps
    _lock = threading.Lock()

    @classmethod
    def enable_pin_auth(cls, custom_pin: str = None):
        with cls._lock:
            cls.auth_enabled = True
            if custom_pin and len(custom_pin.strip()) >= 4:
                cls.pin_code = custom_pin.strip()
            else:
                cls.pin_code = "".join(secrets.choice(string.digits) for _ in range(cls.DEFAULT_PIN_LENGTH))
            cls.authorized_tokens.clear()
            cls.authorized_ips.clear()
            cls.failed_attempts.clear()
            return cls.pin_code

    @classmethod
    def regenerate_pin(cls):
        with cls._lock:
            cls.pin_code = "".join(secrets.choice(string.digits) for _ in range(cls.DEFAULT_PIN_LENGTH))
            cls.authorized_tokens.clear()
            cls.authorized_ips.clear()
            cls.failed_attempts.clear()
            return cls.pin_code

    @classmethod
    def revoke_session(cls, client_ip: str, token: str = ""):
        with cls._lock:
            if token and token in cls.authorized_tokens:
                cls.authorized_tokens.pop(token, None)
            # Purge any tokens associated with this IP
            tokens_to_remove = [t for t, entry in cls.authorized_tokens.items() if entry.get('ip') == client_ip]
            for t in tokens_to_remove:
                cls.authorized_tokens.pop(t, None)
            cls.authorized_ips.pop(client_ip, None)

    @classmethod
    def get_formatted_pin(cls) -> str:
        if len(cls.pin_code) == 8:
            return f"{cls.pin_code[:4]} {cls.pin_code[4:]}"
        return cls.pin_code

    @classmethod
    def disable_pin_auth(cls):
        with cls._lock:
            cls.auth_enabled = False
            cls.pin_code = ""
            cls.authorized_tokens.clear()
            cls.authorized_ips.clear()
            cls.failed_attempts.clear()

    @classmethod
    def is_locked_out(cls, client_ip: str) -> bool:
        # Assumes caller holds cls._lock or called within locked context
        now = time.time()
        attempts = cls.failed_attempts.get(client_ip, [])
        # Filter attempts within window
        valid_attempts = [t for t in attempts if now - t < cls.FAIL_WINDOW]
        cls.failed_attempts[client_ip] = valid_attempts
        if len(valid_attempts) >= cls.MAX_FAILURES:
            # Check if within lockout period since last failure
            if now - valid_attempts[-1] < cls.LOCKOUT_TIME:
                return True
        return False

    @classmethod
    def verify_pin(cls, submitted_pin: str, client_ip: str) -> tuple:
        with cls._lock:
            if not cls.auth_enabled:
                return True, "no-auth-required"

            now = time.time()

            if cls.is_locked_out(client_ip):
                return False, "rate-limited"

            if submitted_pin and secrets.compare_digest(submitted_pin.strip(), cls.pin_code):
                token = secrets.token_hex(16)
                cls.authorized_tokens[token] = {'ip': client_ip, 'created': now}
                cls.authorized_ips[client_ip] = now
                cls.failed_attempts.pop(client_ip, None)
                return True, token

            # Record failed attempt
            cls.failed_attempts.setdefault(client_ip, []).append(now)
            return False, ""

    @classmethod
    def is_authorized(cls, client_ip: str, token: str = "") -> bool:
        with cls._lock:
            if not cls.auth_enabled:
                return True
            if client_ip in ('127.0.0.1', '::1', 'localhost'):
                return True

            now = time.time()

            # If token is provided, authenticate strictly by token
            if token:
                if token in cls.authorized_tokens:
                    entry = cls.authorized_tokens[token]
                    if now - entry.get('created', 0) < cls.TOKEN_TTL:
                        return True
                    else:
                        cls.authorized_tokens.pop(token, None)
                return False

            # Check IP fallback only when no token is provided
            if client_ip in cls.authorized_ips:
                auth_time = cls.authorized_ips[client_ip]
                if now - auth_time < cls.TOKEN_TTL:
                    return True
                else:
                    cls.authorized_ips.pop(client_ip, None)

            return False

