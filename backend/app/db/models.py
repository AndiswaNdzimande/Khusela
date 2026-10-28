"""
TASK-22: SQLAlchemy ORM models.
Tables: sellers, expected_sales, checks, fingerprints.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    JSON,
    String,
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Seller(Base):
    __tablename__ = "sellers"

    id = Column(String, primary_key=True, default=_uuid)
    business_name = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    expected_sales = relationship(
        "ExpectedSale", back_populates="seller", cascade="all, delete-orphan"
    )
    checks = relationship(
        "Check", back_populates="seller", cascade="all, delete-orphan"
    )
    fingerprints = relationship(
        "Fingerprint", back_populates="seller", cascade="all, delete-orphan"
    )


class ExpectedSale(Base):
    __tablename__ = "expected_sales"

    id = Column(String, primary_key=True, default=_uuid)
    seller_id = Column(
        String, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount = Column(Float, nullable=False)          # in cents
    reference = Column(String, nullable=False)
    expected_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    seller = relationship("Seller", back_populates="expected_sales")


class Check(Base):
    __tablename__ = "checks"

    id = Column(String, primary_key=True, default=_uuid)
    seller_id = Column(
        String, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    verdict = Column(String, nullable=False)        # MATCH | WAIT | STOP
    reasons = Column(JSON, nullable=False, default=list)
    raw_file_path = Column(String, nullable=True)   # cleared by the deletion job
    raw_file_uploaded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    seller = relationship("Seller", back_populates="checks")
    fingerprints = relationship(
        "Fingerprint", back_populates="check", cascade="all, delete-orphan"
    )


class Fingerprint(Base):
    __tablename__ = "fingerprints"

    id = Column(String, primary_key=True, default=_uuid)
    seller_id = Column(
        String, ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False
    )
    check_id = Column(
        String, ForeignKey("checks.id", ondelete="CASCADE"), nullable=False
    )
    hash = Column(String, nullable=False)           # hex string of the perceptual hash
    hash_int = Column(BigInteger, nullable=True)    # signed int64 for Hamming distance queries
    reference_hash = Column(String, nullable=True, index=True) # SHA-256 of normalised ref+amt+timestamp
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    seller = relationship("Seller", back_populates="fingerprints")
    check = relationship("Check", back_populates="fingerprints")

    __table_args__ = (Index("ix_fingerprints_hash", "hash"),)
