import json
import base64
from cryptography.fernet import Fernet
from app.config import get_settings


def _get_fernet() -> Fernet:
    settings = get_settings()
    raw = settings.ENCRYPTION_KEY.encode()
    # Pad or truncate to exactly 32 bytes, then base64url-encode for Fernet
    key_bytes = (raw + b"\0" * 32)[:32]
    key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(key)


def encrypt_credentials(credentials: dict) -> str:
    f = _get_fernet()
    data = json.dumps(credentials).encode()
    return f.encrypt(data).decode()


def decrypt_credentials(encrypted: str) -> dict:
    f = _get_fernet()
    data = f.decrypt(encrypted.encode())
    return json.loads(data.decode())
