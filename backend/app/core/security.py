from __future__ import annotations

from datetime import datetime, timezone
from passlib.context import CryptContext
from jose import jwt

from app.config.settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, role: str = "USER", expires_hours: int = 24) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + expires_hours * 3600,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
