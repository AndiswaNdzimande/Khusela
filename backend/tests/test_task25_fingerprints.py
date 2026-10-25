"""
TASK-25: Fingerprint store and near-duplicate detection.
Cases:
  A. Same image from seller A then seller B → flagged for B
  B. Same image uploaded twice by seller A  → NOT flagged
  C. A slightly resized copy               → still detected
  D. An unrelated image                    → not flagged
"""
import io
import uuid

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.fingerprints import (
    HAMMING_THRESHOLD,
    compute_image_hash,
    find_duplicates,
    save_fingerprint,
)
from app.db.models import Check, Seller

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
_Session = sessionmaker(bind=_engine)


def setup_module():
    Base.metadata.create_all(bind=_engine)


def _make_img(color="red", size=(100, 100)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="JPEG")
    return buf.getvalue()


def _add_seller(db, name):
    s = Seller(business_name=name, password_hash="x")
    db.add(s)
    db.flush()
    return s


def _add_check(db, seller_id):
    c = Check(seller_id=seller_id, verdict="MATCH", reasons=[])
    db.add(c)
    db.flush()
    return c


# ---------------------------------------------------------------------------
# Case A: same image, different sellers → flagged
# ---------------------------------------------------------------------------
def test_cross_seller_duplicate_flagged():
    db = _Session()
    seller_a = _add_seller(db, f"SellerA-{uuid.uuid4()}")
    seller_b = _add_seller(db, f"SellerB-{uuid.uuid4()}")

    img = _make_img("green")
    hex_a, int_a = compute_image_hash(img)
    check_a = _add_check(db, seller_a.id)
    save_fingerprint(db, seller_a.id, check_a.id, hex_a, int_a)

    # Seller B uploads the same image
    hex_b, int_b = compute_image_hash(img)
    matches = find_duplicates(db, int_b, seller_b.id)
    assert len(matches) > 0, "Cross-seller duplicate should be flagged"
    db.close()


# ---------------------------------------------------------------------------
# Case B: same image, same seller → NOT flagged
# ---------------------------------------------------------------------------
def test_same_seller_not_flagged():
    db = _Session()
    seller = _add_seller(db, f"SellerC-{uuid.uuid4()}")

    img = _make_img("blue")
    hex1, int1 = compute_image_hash(img)
    check1 = _add_check(db, seller.id)
    save_fingerprint(db, seller.id, check1.id, hex1, int1)

    # Same seller re-uploads the same image
    hex2, int2 = compute_image_hash(img)
    matches = find_duplicates(db, int2, seller.id)
    assert len(matches) == 0, "Same-seller re-upload should NOT be flagged"
    db.close()


# ---------------------------------------------------------------------------
# Case C: slightly resized copy → still detected
# ---------------------------------------------------------------------------
def test_resized_copy_detected():
    db = _Session()
    seller_a = _add_seller(db, f"SellerD-{uuid.uuid4()}")
    seller_b = _add_seller(db, f"SellerE-{uuid.uuid4()}")

    original = _make_img("purple", (100, 100))
    resized = _make_img("purple", (95, 95))   # slight resize

    hex_a, int_a = compute_image_hash(original)
    check_a = _add_check(db, seller_a.id)
    save_fingerprint(db, seller_a.id, check_a.id, hex_a, int_a)

    hex_b, int_b = compute_image_hash(resized)
    matches = find_duplicates(db, int_b, seller_b.id)
    assert len(matches) > 0, "Resized copy should still be detected"
    db.close()


# ---------------------------------------------------------------------------
# Case D: unrelated image → not flagged
# ---------------------------------------------------------------------------
def test_unrelated_image_not_flagged():
    db = _Session()
    seller_a = _add_seller(db, f"SellerF-{uuid.uuid4()}")
    seller_b = _add_seller(db, f"SellerG-{uuid.uuid4()}")

    img_a = _make_img("red", (100, 100))
    img_b = _make_img("cyan", (100, 100))   # visually very different

    hex_a, int_a = compute_image_hash(img_a)
    check_a = _add_check(db, seller_a.id)
    save_fingerprint(db, seller_a.id, check_a.id, hex_a, int_a)

    hex_b, int_b = compute_image_hash(img_b)
    matches = find_duplicates(db, int_b, seller_b.id)
    assert len(matches) == 0, "Unrelated image should not be flagged"
    db.close()
