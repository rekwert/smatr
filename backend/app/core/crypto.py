"""Шифрование API-ключей бирж (Fernet / fallback XOR-obfuscation for MVP)."""

from __future__ import annotations

import base64
import hashlib

from app.config.settings import settings


def _fernet():
    try:
        from cryptography.fernet import Fernet

        digest = hashlib.sha256(settings.secret_key.encode()).digest()
        key = base64.urlsafe_b64encode(digest)
        return Fernet(key)
    except Exception:  # noqa: BLE001
        return None


def encrypt_secret(plain: str) -> str:
    f = _fernet()
    if f is None:
        raw = plain.encode()
        mixed = bytes(b ^ settings.secret_key.encode()[i % len(settings.secret_key)] for i, b in enumerate(raw))
        return "obf:" + base64.urlsafe_b64encode(mixed).decode()
    return f.encrypt(plain.encode()).decode()


def decrypt_secret(token: str) -> str:
    if token.startswith("obf:"):
        mixed = base64.urlsafe_b64decode(token[4:].encode())
        raw = bytes(
            b ^ settings.secret_key.encode()[i % len(settings.secret_key)] for i, b in enumerate(mixed)
        )
        return raw.decode()
    f = _fernet()
    if f is None:
        raise RuntimeError("decrypt unavailable")
    return f.decrypt(token.encode()).decode()
