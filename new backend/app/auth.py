from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import ACCESS_TOKEN_TTL_MINUTES
from app.db.database import get_db
from app.db.models import AuthSession, Seller

security = HTTPBearer(auto_error=False)
AUTH_SECRET = ""


def utcnow() -> datetime:
    return datetime.now(UTC)


def configure_auth_secret(secret: str) -> None:
    global AUTH_SECRET
    AUTH_SECRET = secret


def check_auth_config() -> None:
    if len(AUTH_SECRET.encode("utf-8")) < 32:
        raise HTTPException(
            status_code=503,
            detail="Authentication is unavailable: configure VERIPOP_AUTH_SECRET or JWT_SECRET_KEY with at least 32 bytes.",
        )


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, salt_hex, digest_hex = stored_hash.split("$", 2)
        if algorithm != "scrypt":
            return False
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=len(expected)
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def token_digest(token: str) -> str:
    return hmac.new(AUTH_SECRET.encode("utf-8"), token.encode("ascii"), hashlib.sha256).hexdigest()


def create_session(db: Session, seller_id: str) -> tuple[str, datetime]:
    raw_token = secrets.token_urlsafe(32)
    expires_at = utcnow() + timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES)
    db.add(AuthSession(token_hash=token_digest(raw_token), seller_id=seller_id, expires_at=expires_at))
    db.commit()
    return raw_token, expires_at


def require_seller(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[Session, Depends(get_db)],
) -> Seller:
    check_auth_config()
    if credentials is None:
        raise HTTPException(status_code=401, detail="Bearer access token required.")
    session = db.get(AuthSession, token_digest(credentials.credentials))
    if session is None:
        raise HTTPException(status_code=401, detail="Invalid or expired access token.")
    if session.expires_at <= utcnow():
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid or expired access token.")
    seller = db.get(Seller, session.seller_id)
    if seller is None:
        raise HTTPException(status_code=401, detail="Invalid or expired access token.")
    return seller
