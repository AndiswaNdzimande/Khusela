"""
TASK-23: Seller authentication.
POST /auth/register  – create account (201) or 409 if name taken
POST /auth/login     – return JWT bearer token (200) or 401
"""
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Seller
from app.schemas.auth import LoginRequest, RegisterRequest, RegisterResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Config – read from environment, no hard-coded defaults for production values
# ---------------------------------------------------------------------------
SECRET_KEY: str = os.environ["JWT_SECRET_KEY"]          # must be set; crash loudly if not
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def _verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(seller_id: str, business_name: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": seller_id,
        "name": business_name,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# Dependency: resolve the current seller from the Authorization header
# Raises 401 on missing / invalid / expired token.
# ---------------------------------------------------------------------------
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer()


def get_current_seller(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Seller:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        seller_id: str = payload.get("sub")
        if seller_id is None:
            raise JWTError("missing sub")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    seller = db.get(Seller, seller_id)
    if seller is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Seller not found")
    return seller


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(Seller).filter(Seller.business_name == body.business_name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Business name already registered",
        )
    seller = Seller(
        business_name=body.business_name,
        password_hash=_hash_password(body.password),
    )
    db.add(seller)
    db.commit()
    db.refresh(seller)
    return RegisterResponse(id=seller.id, business_name=seller.business_name)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    seller = db.query(Seller).filter(Seller.business_name == body.business_name).first()
    if not seller or not _verify_password(body.password, seller.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = _create_token(seller.id, seller.business_name)
    return TokenResponse(access_token=token)
