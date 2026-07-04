"""JWT authentication utilities.

We use short-lived access tokens (30 min) paired with longer-lived refresh
tokens (7 days). The access token carries the user ID and org ID so most
API calls don't need a database lookup for authorization.
"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from packages.config import get_settings
from packages.db import get_session
from packages.db.models.tenant import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


class TokenPayload(BaseModel):
    user_id: str
    org_id: str
    exp: datetime


class AuthContext(BaseModel):
    """Injected into route handlers via Depends(get_current_user)."""
    user_id: uuid.UUID
    org_id: uuid.UUID


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: uuid.UUID, org_id: uuid.UUID) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "org": str(org_id),
        "exp": expires,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: uuid.UUID, org_id: uuid.UUID) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_ttl_days)
    payload = {
        "sub": str(user_id),
        "org": str(org_id),
        "exp": expires,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> AuthContext:
    payload = _decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Expected access token")
    return AuthContext(
        user_id=uuid.UUID(payload["sub"]),
        org_id=uuid.UUID(payload["org"]),
    )
