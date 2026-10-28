from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import check_auth_config, create_session, hash_password, require_seller, utcnow, verify_password
from app.config import ACCESS_TOKEN_TTL_MINUTES
from app.db.database import get_db
from app.db.models import Seller

router = APIRouter(tags=["khusela-auth"])


class KhuselaRegisterRequest(BaseModel):
    business_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)


class KhuselaLoginRequest(BaseModel):
    business_name: str
    password: str


class KhuselaAuthResponse(BaseModel):
    access_token: str
    token: str
    token_type: str = "bearer"
    expires_in: int
    seller_id: str
    id: str
    business_name: str


def _register(body: KhuselaRegisterRequest, db: Session) -> KhuselaAuthResponse:
    check_auth_config()
    name = body.business_name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="business_name must not be blank")
    existing = db.query(Seller).filter(Seller.business_name == name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Business name already registered")
    seller = Seller(business_name=name, password_hash=hash_password(body.password))
    db.add(seller)
    db.commit()
    db.refresh(seller)
    token, expires_at = create_session(db, seller.id)
    return KhuselaAuthResponse(
        access_token=token,
        token=token,
        expires_in=int((expires_at - utcnow()).total_seconds()) or ACCESS_TOKEN_TTL_MINUTES * 60,
        seller_id=seller.id,
        id=seller.id,
        business_name=seller.business_name,
    )


def _login(body: KhuselaLoginRequest, db: Session) -> KhuselaAuthResponse:
    check_auth_config()
    seller = db.query(Seller).filter(Seller.business_name == body.business_name.strip()).first()
    if seller is None or not verify_password(body.password, seller.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_at = create_session(db, seller.id)
    return KhuselaAuthResponse(
        access_token=token,
        token=token,
        expires_in=int((expires_at - utcnow()).total_seconds()) or ACCESS_TOKEN_TTL_MINUTES * 60,
        seller_id=seller.id,
        id=seller.id,
        business_name=seller.business_name,
    )


@router.post("/auth/register", response_model=KhuselaAuthResponse, status_code=201)
def register(body: KhuselaRegisterRequest, db: Annotated[Session, Depends(get_db)]) -> KhuselaAuthResponse:
    return _register(body, db)


@router.post("/api/auth/register", response_model=KhuselaAuthResponse, status_code=201)
def register_api(body: KhuselaRegisterRequest, db: Annotated[Session, Depends(get_db)]) -> KhuselaAuthResponse:
    return _register(body, db)


@router.post("/auth/login", response_model=KhuselaAuthResponse)
def login(body: KhuselaLoginRequest, db: Annotated[Session, Depends(get_db)]) -> KhuselaAuthResponse:
    return _login(body, db)


@router.post("/api/auth/login", response_model=KhuselaAuthResponse)
def login_api(body: KhuselaLoginRequest, db: Annotated[Session, Depends(get_db)]) -> KhuselaAuthResponse:
    return _login(body, db)


@router.get("/auth/me")
def me(seller: Annotated[Seller, Depends(require_seller)]) -> dict[str, str]:
    return {"seller_id": seller.id, "business_name": seller.business_name, "email": seller.email or ""}
