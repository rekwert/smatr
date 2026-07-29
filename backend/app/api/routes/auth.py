from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.core.security import ALGORITHM, create_access_token, hash_password, verify_password
from app.database.connection import get_db
from app.database.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


class RegisterIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class ProfileOut(BaseModel):
    id: int
    email: str
    username: Optional[str] = None
    role: str
    subscription: str
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(401, detail="Требуется авторизация")
    try:
        payload: dict[str, Any] = jwt.decode(
            creds.credentials, settings.secret_key, algorithms=[ALGORITHM]
        )
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(401, detail="Недействительный токен")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(401, detail="Пользователь не найден")
    return user


@router.post("/register", response_model=TokenOut)
async def register(payload: RegisterIn, db: AsyncSession = Depends(get_db)):
    existing = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(400, detail="Email уже зарегистрирован")
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role="USER",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(str(user.id), role=user.role)
    return TokenOut(access_token=token, role=user.role)


@router.post("/login", response_model=TokenOut)
async def login(payload: RegisterIn, db: AsyncSession = Depends(get_db)):
    user = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, detail="Неверный email или пароль")
    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    token = create_access_token(str(user.id), role=user.role)
    return TokenOut(access_token=token, role=user.role)


@router.get("/profile", response_model=ProfileOut)
async def profile(user: User = Depends(get_current_user)):
    return ProfileOut(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role,
        subscription=user.subscription,
        created_at=user.created_at,
        last_login=user.last_login,
    )


@router.get("/me", response_model=ProfileOut)
async def me(user: User = Depends(get_current_user)):
    return ProfileOut(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role,
        subscription=user.subscription,
        created_at=user.created_at,
        last_login=user.last_login,
    )
