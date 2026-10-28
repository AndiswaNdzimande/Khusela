from __future__ import annotations

import hashlib
import os
import re
import struct
import uuid
import zlib
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app import auth as auth_mod
from app.auth import (
    check_auth_config,
    create_session,
    hash_password,
    require_seller,
    security,
    token_digest,
    utcnow,
    verify_password,
)
from app.config import (
    ACCESS_TOKEN_TTL_MINUTES,
    ALLOWED_ORIGINS,
    APP_NAME,
    AUTH_SECRET as CONFIG_AUTH_SECRET,
    DATA_DIR as CONFIG_DATA_DIR,
    MAX_IMAGE_PIXELS,
    MAX_PDF_PAGES,
    MAX_UPLOAD_BYTES,
)
from app.db.database import get_db, init_db
from app.db.models import AuthSession, Document, Seller
from app.routers.khusela_auth import router as khusela_auth_router
from app.routers.khusela_check import router as khusela_check_router

DATA_DIR = Path(CONFIG_DATA_DIR)
AUTH_SECRET = CONFIG_AUTH_SECRET
auth_mod.configure_auth_secret(AUTH_SECRET)


class JobStatus(str, Enum):
    COMPLETED = "COMPLETED"


class RiskLevel(str, Enum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Finding(BaseModel):
    rule_id: str
    category: str
    severity: str
    explanation: str
    confidence: float = Field(ge=0, le=1)
    requires_human_review: bool = True


class VerificationResult(BaseModel):
    verification_id: str
    status: JobStatus
    document_type: str
    risk_score: int | None = Field(default=None, ge=0, le=100)
    risk_level: RiskLevel
    limitations: list[str]
    findings: list[Finding] = Field(default_factory=list)
    document_sha256: str
    created_at: datetime


class UploadResponse(BaseModel):
    document_id: str
    verification_id: str
    status: JobStatus
    message: str


class StoredDocument(BaseModel):
    document_id: str
    verification_id: str
    owner_id: str
    status: JobStatus
    result: VerificationResult | None
    content_type: str
    original_name: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str


class User(BaseModel):
    user_id: str
    email: EmailStr
    password_hash: str


class DocumentRejected(ValueError):
    pass


def _sync_auth_secret() -> None:
    auth_mod.configure_auth_secret(AUTH_SECRET)


def _check_auth_config() -> None:
    _sync_auth_secret()
    check_auth_config()


def identify_signature(data: bytes) -> str | None:
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def check_png(data: bytes) -> list[Finding]:
    findings: list[Finding] = []
    offset = 8
    seen_ihdr = seen_iend = False
    width = height = 0
    chunk_count = 0
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        end = offset + 12 + length
        if length > MAX_UPLOAD_BYTES or end > len(data):
            raise DocumentRejected("PNG contains an incomplete or invalid chunk.")
        chunk_data = data[offset + 8 : offset + 8 + length]
        recorded_crc = struct.unpack(">I", data[offset + 8 + length : end])[0]
        actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
        if recorded_crc != actual_crc:
            findings.append(Finding(
                rule_id="PNG_CHUNK_CRC_MISMATCH", category="FILE_INTEGRITY", severity="MEDIUM",
                explanation="A PNG chunk checksum does not match its content; the file may be damaged or altered.",
                confidence=0.98,
            ))
        if chunk_count == 0 and chunk_type != b"IHDR":
            raise DocumentRejected("PNG is missing its required IHDR header chunk.")
        if chunk_type == b"IHDR":
            if seen_ihdr or length != 13:
                raise DocumentRejected("PNG has an invalid IHDR chunk.")
            width, height = struct.unpack(">II", chunk_data[:8])
            if width == 0 or height == 0 or width * height > MAX_IMAGE_PIXELS:
                raise DocumentRejected("PNG dimensions are invalid or exceed the pixel limit.")
            seen_ihdr = True
        if chunk_type == b"IEND":
            if length != 0:
                raise DocumentRejected("PNG IEND chunk is invalid.")
            seen_iend = True
            offset = end
            break
        offset = end
        chunk_count += 1
    if not seen_ihdr or not seen_iend:
        raise DocumentRejected("PNG is truncated or has no IEND chunk.")
    if offset < len(data):
        findings.append(Finding(
            rule_id="PNG_TRAILING_DATA", category="FILE_STRUCTURE", severity="LOW",
            explanation="Data occurs after the PNG IEND marker. This can occur in benign workflows and needs review.",
            confidence=0.99,
        ))
    return findings


def check_jpeg(data: bytes) -> list[Finding]:
    if len(data) < 4 or not data.endswith(b"\xff\xd9"):
        raise DocumentRejected("JPEG is truncated or missing its end-of-image marker.")
    findings: list[Finding] = []
    if data.count(b"\xff\xd8") > 1:
        findings.append(Finding(
            rule_id="JPEG_MULTIPLE_SOI_MARKERS", category="FILE_STRUCTURE", severity="MEDIUM",
            explanation="Additional JPEG start markers were found within the file; this can indicate appended or unusual content.",
            confidence=0.9,
        ))
    if data[:-2].find(b"\x00\x00\x00\x00\x00\x00\x00\x00", 2) >= 0:
        findings.append(Finding(
            rule_id="JPEG_ZERO_RUN", category="FILE_STRUCTURE", severity="INFO",
            explanation="A long zero-byte run was found; this is a weak structural signal and is not proof of editing.",
            confidence=0.3,
        ))
    return findings


def check_pdf(data: bytes) -> list[Finding]:
    if len(data) < 20 or b"%%EOF" not in data[-2048:]:
        raise DocumentRejected("PDF is truncated or lacks a valid end marker.")
    if b"/Encrypt" in data:
        raise DocumentRejected("Password-protected or encrypted PDF is not currently supported.")
    if b"/JavaScript" in data or b"/JS " in data or b"/Launch" in data:
        raise DocumentRejected("PDF includes active content that this prototype does not accept.")
    findings: list[Finding] = []

    # --- Incremental update / appended revision detection ---
    eof_count = data.count(b"%%EOF")
    has_appended_pdf = bool(re.search(rb"startxref\s+\d+\s+%%EOF.{1,256}%PDF-", data, re.DOTALL))
    if eof_count > 1 or has_appended_pdf:
        findings.append(Finding(
            rule_id="PDF_INCREMENTAL_OR_TRAILING_REVISION",
            category="FILE_STRUCTURE",
            severity="MEDIUM",
            explanation=(
                "The PDF contains multiple end-of-file markers or appended revisions. "
                "This can indicate that content was added after the original was created — "
                "a common pattern in tampered bank letters and confirmation documents. "
                "Verify the original directly with the issuing institution."
            ),
            confidence=0.85,
        ))

    # --- Trailing non-whitespace bytes after the last %%EOF ---
    # Legitimate PDFs end with %%EOF followed by at most a newline.
    # Appended text (e.g. a forged account number) leaves readable bytes after it.
    last_eof = data.rfind(b"%%EOF")
    if last_eof != -1:
        tail = data[last_eof + 5:].strip()  # skip "%%EOF" (5 bytes) and whitespace
        if tail:
            # Check whether the tail contains printable ASCII — a strong signal of
            # appended text content rather than benign padding.
            printable = sum(1 for b in tail if 0x20 <= b <= 0x7E)
            if len(tail) > 0 and printable / max(len(tail), 1) > 0.5:
                findings.append(Finding(
                    rule_id="PDF_APPENDED_TEXT_AFTER_EOF",
                    category="FILE_INTEGRITY",
                    severity="HIGH",
                    explanation=(
                        "Readable text was found after the PDF end-of-file marker. "
                        "This is a strong indicator of manual tampering — content may have "
                        "been appended to alter the document after it was originally issued. "
                        "Do not rely on this document without direct verification from the bank."
                    ),
                    confidence=0.92,
                ))

    # --- Cross-reference stream vs table inconsistency (basic check) ---
    # A PDF that mixes xref tables and xref streams without a valid hybrid
    # structure is a common artefact of amateur PDF editors.
    has_xref_table = bool(re.search(rb"\bxref\b", data))
    has_xref_stream = bool(re.search(rb"/Type\s*/XRef\b", data))
    if has_xref_table and has_xref_stream:
        findings.append(Finding(
            rule_id="PDF_MIXED_XREF_STRUCTURE",
            category="FILE_STRUCTURE",
            severity="LOW",
            explanation=(
                "The PDF mixes cross-reference tables and streams — a pattern sometimes "
                "seen in documents edited with consumer PDF tools. This alone is not proof "
                "of tampering but warrants closer review."
            ),
            confidence=0.6,
        ))

    page_count = len(re.findall(rb"/Type\s*/Page\b", data))
    if page_count > MAX_PDF_PAGES:
        raise DocumentRejected(f"PDF exceeds the configured maximum of {MAX_PDF_PAGES} pages.")
    if page_count == 0:
        findings.append(Finding(
            rule_id="PDF_PAGE_COUNT_UNAVAILABLE",
            category="FILE_STRUCTURE",
            severity="INFO",
            explanation="Page count could not be reliably determined by the conservative PDF scanner.",
            confidence=0.95,
        ))
    return findings


def make_screening_result(verification_id: str, digest: str, content_type: str, data: bytes) -> VerificationResult:
    try:
        if content_type == "image/png":
            findings = check_png(data)
        elif content_type == "image/jpeg":
            findings = check_jpeg(data)
        else:
            findings = check_pdf(data)
    except DocumentRejected as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    findings.append(Finding(
        rule_id="AUTHENTICITY_NOT_VERIFIED", category="INSUFFICIENT_EVIDENCE", severity="INFO",
        explanation=(
            "Structural screening completed, but no OCR, trusted source comparison, bank/issuer validation, "
            "or validated manipulation detector is configured. This result cannot establish authenticity."
        ),
        confidence=1.0,
    ))

    # Derive risk level from the highest severity finding.
    severity_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "INFO": 0}
    max_severity = max((severity_order.get(f.severity, 0) for f in findings), default=0)
    if max_severity >= 3:
        risk_level = RiskLevel.HIGH
        risk_score = 85
    elif max_severity == 2:
        risk_level = RiskLevel.MEDIUM
        risk_score = 55
    elif max_severity == 1:
        risk_level = RiskLevel.LOW
        risk_score = 25
    else:
        risk_level = RiskLevel.INSUFFICIENT_EVIDENCE
        risk_score = None

    return VerificationResult(
        verification_id=verification_id,
        status=JobStatus.COMPLETED,
        document_type=content_type,
        risk_score=risk_score,
        risk_level=risk_level,
        limitations=[
            "Structural anomaly checks are screening signals, not a counterfeit classifier.",
            "No OCR, layout comparison, image manipulation model, or authoritative provider was run.",
            "No bank transaction or identity issuer was contacted.",
            "Anomalies may have benign causes; absence of findings does not prove authenticity.",
        ],
        findings=findings,
        document_sha256=digest,
        created_at=utcnow(),
    )


def _seller_to_user(seller: Seller) -> User:
    return User(user_id=seller.id, email=seller.email or f"{seller.id}@users.local", password_hash=seller.password_hash)


def _document_from_row(row: Document) -> StoredDocument:
    result = VerificationResult.model_validate(row.result) if row.result else None
    return StoredDocument(
        document_id=row.document_id,
        verification_id=row.verification_id,
        owner_id=row.owner_id,
        status=JobStatus(row.status),
        result=result,
        content_type=row.content_type,
        original_name=row.original_name,
    )


app = FastAPI(
    title=APP_NAME,
    version="0.3.0",
    description=(
        "Khusela-compatible document screening API with SQLite persistence. "
        "Structural checks and fingerprints are not proof of authenticity, fraud, payment, or identity."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)
app.include_router(khusela_auth_router)
app.include_router(khusela_check_router)
init_db()

_scheduler = None


@app.on_event("startup")
def on_startup() -> None:
    global _scheduler
    _sync_auth_secret()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    init_db()

    from app.config import START_SCHEDULER
    if START_SCHEDULER:
        try:
            from app.scheduler import start_scheduler
            _scheduler = start_scheduler()
        except Exception as exc:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).warning(
                "Could not start deletion scheduler: %s", exc
            )


@app.on_event("shutdown")
def on_shutdown() -> None:
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": APP_NAME}


@app.post("/api/v1/auth/register", response_model=AuthResponse, status_code=201)
def register(request: RegisterRequest, db: Annotated[Session, Depends(get_db)]) -> AuthResponse:
    _check_auth_config()
    email = str(request.email).lower()
    if db.query(Seller).filter((Seller.email == email) | (Seller.business_name == email)).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")
    seller = Seller(business_name=email, email=email, password_hash=hash_password(request.password))
    db.add(seller)
    db.commit()
    db.refresh(seller)
    token, expires_at = create_session(db, seller.id)
    return AuthResponse(
        access_token=token,
        expires_in=int((expires_at - utcnow()).total_seconds()),
        user_id=seller.id,
    )


@app.post("/api/v1/auth/login", response_model=AuthResponse)
def login(request: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> AuthResponse:
    _check_auth_config()
    email = str(request.email).lower()
    seller = db.query(Seller).filter((Seller.email == email) | (Seller.business_name == email)).first()
    if seller is None or not verify_password(request.password, seller.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    token, expires_at = create_session(db, seller.id)
    return AuthResponse(
        access_token=token,
        expires_in=int((expires_at - utcnow()).total_seconds()),
        user_id=seller.id,
    )


@app.post("/api/v1/auth/logout", status_code=204)
def logout(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[Seller, Depends(require_seller)],
) -> None:
    _sync_auth_secret()
    if credentials:
        session = db.get(AuthSession, token_digest(credentials.credentials))
        if session:
            db.delete(session)
            db.commit()


@app.get("/api/v1/auth/me")
def auth_me(user: Annotated[Seller, Depends(require_seller)]) -> dict[str, str]:
    return {"user_id": user.id, "email": user.email or user.business_name}


@app.post("/api/v1/documents", response_model=UploadResponse, status_code=202)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    user: Annotated[Seller, Depends(require_seller)],
    db: Annotated[Session, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> UploadResponse:
    if idempotency_key and (len(idempotency_key) > 200 or not re.fullmatch(r"[\w.:-]+", idempotency_key)):
        raise HTTPException(status_code=400, detail="Invalid Idempotency-Key.")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    document_id = str(uuid.uuid4())
    verification_id = str(uuid.uuid4())
    path = DATA_DIR / f"{document_id}.upload"
    digest = hashlib.sha256()
    contents = bytearray()
    try:
        with path.open("xb") as output:
            while chunk := await file.read(64 * 1024):
                if len(contents) + len(chunk) > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="File exceeds the upload size limit.")
                contents.extend(chunk)
                digest.update(chunk)
                output.write(chunk)
        content_type = identify_signature(bytes(contents[:8]))
        if content_type is None:
            raise HTTPException(status_code=415, detail="Only PDF, PNG, and JPEG files are supported.")
        result = make_screening_result(verification_id, digest.hexdigest(), content_type, bytes(contents))
        db.add(
            Document(
                document_id=document_id,
                verification_id=verification_id,
                owner_id=user.id,
                status=JobStatus.COMPLETED.value,
                result=result.model_dump(mode="json"),
                content_type=content_type,
                original_name=Path(file.filename or "upload").name[:255],
            )
        )
        db.commit()
        return UploadResponse(
            document_id=document_id,
            verification_id=verification_id,
            status=JobStatus.COMPLETED,
            message="Structural screening complete. Authenticity is not verified; review findings and limitations.",
        )
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@app.get("/api/v1/documents/{document_id}", response_model=StoredDocument)
def get_document(document_id: str, user: Annotated[Seller, Depends(require_seller)], db: Annotated[Session, Depends(get_db)]) -> StoredDocument:
    document = db.get(Document, document_id)
    if document is None or document.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Document not found.")
    return _document_from_row(document)


@app.get("/api/v1/verifications/{verification_id}", response_model=VerificationResult)
def get_verification(
    verification_id: str,
    user: Annotated[Seller, Depends(require_seller)],
    db: Annotated[Session, Depends(get_db)],
) -> VerificationResult:
    document = db.query(Document).filter(Document.verification_id == verification_id, Document.owner_id == user.id).first()
    if document is None or not document.result:
        raise HTTPException(status_code=404, detail="Verification not found.")
    return VerificationResult.model_validate(document.result)


@app.delete("/api/v1/documents/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    user: Annotated[Seller, Depends(require_seller)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    document = db.get(Document, document_id)
    if document is None or document.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Document not found.")
    db.delete(document)
    db.commit()
    (DATA_DIR / f"{document_id}.upload").unlink(missing_ok=True)
