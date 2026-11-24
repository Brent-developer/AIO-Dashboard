from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from config import settings


password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def verify_admin(username: str, password: str) -> bool:
    expected_user = os.getenv("ADMIN_USERNAME", "admin")
    password_hash = os.getenv("ADMIN_PASSWORD_HASH")
    if username != expected_user:
        return False
    if password_hash:
        return password_context.verify(password, password_hash)
    return password == os.getenv("ADMIN_PASSWORD", "admin")


def create_token(subject: str, token_type: str) -> str:
    now = datetime.now(timezone.utc)
    expires = now + (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    return jwt.encode(
        {"sub": subject, "type": token_type, "iat": now, "exp": expires},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def token_pair(subject: str) -> dict[str, str]:
    return {
        "access_token": create_token(subject, "access"),
        "refresh_token": create_token(subject, "refresh"),
        "token_type": "bearer",
    }


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from exc
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return payload


async def current_user(token: str = Depends(oauth2_scheme)) -> str:
    return str(decode_token(token, "access")["sub"])
