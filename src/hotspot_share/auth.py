import secrets
import string
import time

class AuthManager:
    auth_enabled = False
    pin_code = ""
    authorized_tokens = {}  # token -> {'ip': ip, 'created': timestamp}
    authorized_ips = set()

    @classmethod
    def enable_pin_auth(cls, custom_pin: str = None):
        cls.auth_enabled = True
        if custom_pin and len(custom_pin) >= 4:
            cls.pin_code = custom_pin
        else:
            cls.pin_code = "".join(secrets.choice(string.digits) for _ in range(4))
        cls.authorized_tokens.clear()
        cls.authorized_ips.clear()
        return cls.pin_code

    @classmethod
    def disable_pin_auth(cls):
        cls.auth_enabled = False
        cls.pin_code = ""
        cls.authorized_tokens.clear()
        cls.authorized_ips.clear()

    @classmethod
    def verify_pin(cls, submitted_pin: str, client_ip: str) -> tuple:
        if not cls.auth_enabled:
            return True, "no-auth-required"

        if submitted_pin and submitted_pin.strip() == cls.pin_code:
            token = secrets.token_hex(16)
            cls.authorized_tokens[token] = {'ip': client_ip, 'created': time.time()}
            cls.authorized_ips.add(client_ip)
            return True, token
        return False, ""

    @classmethod
    def is_authorized(cls, client_ip: str, token: str = "") -> bool:
        if not cls.auth_enabled:
            return True
        if client_ip in ('127.0.0.1', '::1', 'localhost'):
            return True
        if client_ip in cls.authorized_ips:
            return True
        if token and token in cls.authorized_tokens:
            return True
        return False
