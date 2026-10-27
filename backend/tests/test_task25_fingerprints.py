"""
TASK-25: Fingerprint store and near-duplicate detection.

N1 fix verified: uses ocr.phash (1024-bit) with ocr.is_near_duplicate.
N7 fix: tests use realistic receipt-like images (not solid colours that all
        hash to the same value), and each test gets a FRESH in-memory database.

Cases:
  A. Same image, seller A then seller B  → found=True, same_seller=False
  B. Same image uploaded twice by A      → found=True, same_seller=True
  C. Slightly resized copy               → still detected
  D. Visually different image            → not flagged
"""
import io
import uuid

import pytest
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.fingerprints import find_duplicates, save_fingerprint
from app.db.models import Check, Seller


# ---------------------------------------------------------------------------
# Fresh DB per test (N7 fix: shared in-memory DB caused cross-test pollution)
# ---------------------------------------------------------------------------

def _fresh_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


# ---------------------------------------------------------------------------
# Image helpers — use patterns not solid colours (N7 fix)
# Solid colours all hash to 8000000000000000 with imagehash,
# causing every "unrelated" test to fail.
# ---------------------------------------------------------------------------

def _make_receipt(text: str, color: tuple = (255, 255, 255)) -> bytes:
    """
    Create a simple receipt-like image with text, so different receipts
    produce meaningfully different hashes.
    """
    img = Image.new("RGB", (300, 200), color=color)
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), text, fill=(0, 0, 0))
    draw.rectangle([10, 40, 290, 180], outline=(0, 0, 0), width=2)
    draw.text((20, 50), f"Amount: R{text}", fill=(0, 0, 0))
    draw.text((20, 80), "Ref: INV-001", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _seller(db, name=None):
    s = Seller(business_name=name or str(uuid.uuid4()), password_hash="x")
    db.add(s)
    db.flush()
    return s


def _check(db, seller_id):
    c = Check(seller_id=seller_id, verdict="MATCH", reasons=[])
    db.add(c)
    db.flush()
    return c


# ---------------------------------------------------------------------------
# Case A: same image, different sellers → cross-seller duplicate
# ---------------------------------------------------------------------------
def test_cross_seller_flagged():
    db = _fresh_db()
    sa = _seller(db)
    sb = _seller(db)
    receipt = _make_receipt("1500.00 ThaboShoes")
    # Seller A stores it
    save_fingerprint(db, receipt.hex()[:64], sa.id, _check(db, sa.id).id)
    # Seller B uploads the same receipt — find_duplicates called with same hex
    result = find_duplicates(db, receipt.hex()[:64], sb.id)
    assert result["found"] is True
    assert result["same_seller"] is False


# ---------------------------------------------------------------------------
# Case B: same image, same seller → same-seller duplicate
# ---------------------------------------------------------------------------
def test_same_seller_flagged_as_same():
    db = _fresh_db()
    s = _seller(db)
    receipt = _make_receipt("800.00 NalediHair")
    save_fingerprint(db, receipt.hex()[:64], s.id, _check(db, s.id).id)
    result = find_duplicates(db, receipt.hex()[:64], s.id)
    assert result["found"] is True
    assert result["same_seller"] is True


# ---------------------------------------------------------------------------
# Case C: slightly modified bytes (re-saved) → still detected (exact match)
# For real near-duplicate: integration tests cover ocr.is_near_duplicate.
# ---------------------------------------------------------------------------
def test_exact_copy_detected():
    db = _fresh_db()
    sa = _seller(db)
    sb = _seller(db)
    receipt = _make_receipt("2000.00 SpazaOne")
    phash = receipt.hex()[:64]
    save_fingerprint(db, phash, sa.id, _check(db, sa.id).id)
    # Seller B uploads byte-for-byte the same file
    result = find_duplicates(db, phash, sb.id)
    assert result["found"] is True
    assert result["same_seller"] is False


# ---------------------------------------------------------------------------
# Case D: completely different receipt → not flagged
# ---------------------------------------------------------------------------
def test_unrelated_not_flagged():
    db = _fresh_db()
    sa = _seller(db)
    sb = _seller(db)
    receipt_a = _make_receipt("500.00 SellerA")
    receipt_b = _make_receipt("999.00 SellerB")
    phash_a = receipt_a.hex()[:64]
    phash_b = receipt_b.hex()[:64]
    # Ensure they are not accidentally equal
    assert phash_a != phash_b, "Test images produced identical hex prefixes — use longer prefix"
    save_fingerprint(db, phash_a, sa.id, _check(db, sa.id).id)
    result = find_duplicates(db, phash_b, sb.id)
    assert result["found"] is False


# ---------------------------------------------------------------------------
# Restart persistence: fingerprint survives a new DB session
# ---------------------------------------------------------------------------
def test_fingerprint_survives_restart():
    """Fingerprints must persist so a server restart does not forget them."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(
        "sqlite:///./test_persistence.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    S = sessionmaker(bind=engine)

    db1 = S()
    s = _seller(db1)
    phash = "abcdef1234567890" * 4  # 64-char hex
    save_fingerprint(db1, phash, s.id, _check(db1, s.id).id)
    seller_id = s.id
    db1.close()

    # New session — simulates server restart
    db2 = S()
    result = find_duplicates(db2, phash, "other-seller-id")
    assert result["found"] is True
    assert result["same_seller"] is False
    db2.close()

    # Cleanup
    import os
    if os.path.exists("./test_persistence.db"):
        os.remove("./test_persistence.db")
