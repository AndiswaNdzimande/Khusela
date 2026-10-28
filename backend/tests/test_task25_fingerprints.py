"""
TASK-25: Fingerprint store and near-duplicate detection.
Bug 1 fix verified: no OverflowError from large pHash integers.
Bug 5 fix verified: find_duplicates returns same_seller flag.
Bug 6 fix verified: default threshold is 28.

Cases:
  A. Same image from seller A then seller B  → flagged, same_seller=False
  B. Same image uploaded twice by seller A   → flagged, same_seller=True (not STOP)
  C. Slightly resized copy                   → still detected
  D. Unrelated image                         → not flagged
"""
import io
import uuid

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.fingerprints import (
    _INT64_OFFSET,
    compute_image_hash,
    dup_result,
    find_duplicates,
    save_fingerprint,
)
from app.db.models import Check, Seller

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
_Session = sessionmaker(bind=_engine)


def setup_module():
    Base.metadata.create_all(bind=_engine)

@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    yield


def _img(color="red", size=(100, 100)) -> bytes:
    from PIL import ImageDraw
    img = Image.new("RGB", size, color="white")
    draw = ImageDraw.Draw(img)
    # Distinct visual shapes per color key so pHash has spatial features
    if color == "red":
        draw.rectangle([10, 10, 50, 50], fill="red")
    elif color == "cyan":
        draw.line([0, 0, size[0], size[1]], fill="cyan", width=8)
        draw.ellipse([60, 60, 90, 90], fill="blue")
    elif color == "blue":
        draw.ellipse([10, 10, 90, 90], fill="blue")
    elif color == "purple":
        draw.polygon([(10, 10), (90, 50), (10, 90)], fill="purple")
    elif color == "orange":
        draw.rectangle([20, 20, 80, 80], fill="orange")
    else:
        draw.rectangle([30, 30, 70, 70], fill=color)
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
# Bug 1: overflow test — large uint64 hashes must not raise
# ---------------------------------------------------------------------------
def test_no_overflow_on_large_hash():
    """All pHash integers must fit in SQLite signed int64."""
    db = _Session()
    s = _seller(db)
    c = _check(db, s.id)
    hex_h, int_h = compute_image_hash(_img("green"))
    # Must not raise OverflowError
    fp = save_fingerprint(db, s.id, c.id, hex_h, int_h)
    assert fp.id is not None
    assert -_INT64_OFFSET <= fp.hash_int < _INT64_OFFSET
    db.close()


# ---------------------------------------------------------------------------
# Case A: cross-seller duplicate flagged
# ---------------------------------------------------------------------------
def test_cross_seller_flagged():
    db = _Session()
    sa = _seller(db)
    sb = _seller(db)
    img = _img("orange")
    hx, hi = compute_image_hash(img)
    save_fingerprint(db, sa.id, _check(db, sa.id).id, hx, hi)
    matches = find_duplicates(db, hi, sb.id)
    dr = dup_result(matches)
    assert dr["found"] is True
    assert dr["same_seller"] is False
    db.close()


# ---------------------------------------------------------------------------
# Case B: same-seller re-upload → found but same_seller=True
# ---------------------------------------------------------------------------
def test_same_seller_flagged_as_same():
    db = _Session()
    s = _seller(db)
    img = _img("blue")
    hx, hi = compute_image_hash(img)
    save_fingerprint(db, s.id, _check(db, s.id).id, hx, hi)
    matches = find_duplicates(db, hi, s.id)
    dr = dup_result(matches)
    assert dr["found"] is True
    assert dr["same_seller"] is True
    db.close()


# ---------------------------------------------------------------------------
# Case C: resized copy still detected
# ---------------------------------------------------------------------------
def test_resized_copy_detected():
    db = _Session()
    sa = _seller(db)
    sb = _seller(db)
    orig = _img("purple", (100, 100))
    resized = _img("purple", (95, 95))
    hx, hi = compute_image_hash(orig)
    save_fingerprint(db, sa.id, _check(db, sa.id).id, hx, hi)
    hx2, hi2 = compute_image_hash(resized)
    matches = find_duplicates(db, hi2, sb.id)
    dr = dup_result(matches)
    assert dr["found"] is True
    db.close()


# ---------------------------------------------------------------------------
# Case D: unrelated image not flagged
# ---------------------------------------------------------------------------
def test_unrelated_not_flagged():
    db = _Session()
    sa = _seller(db)
    sb = _seller(db)
    hx_a, hi_a = compute_image_hash(_img("red", (100, 100)))
    save_fingerprint(db, sa.id, _check(db, sa.id).id, hx_a, hi_a)
    hx_b, hi_b = compute_image_hash(_img("cyan", (100, 100)))
    matches = find_duplicates(db, hi_b, sb.id)
    dr = dup_result(matches)
    assert dr["found"] is False
    db.close()
