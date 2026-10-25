"""
TASK-25: Fingerprint computation, storage and near-duplicate lookup.

Images → 64-bit perceptual hash (imagehash.phash)
PDFs   → normalised SHA-256 (placeholder; full parse via TASK-27 sandbox)

Bug fixes (v4 report):
  Bug 1: SQLite INTEGER is signed 64-bit (max 2^63-1).  The raw pHash uint64
         can exceed this, causing OverflowError on ~50% of images.
         Fix: store (value - 2^63) so the range shifts to [-2^63, 2^63-1].
         Hamming distance still works correctly on XOR of shifted values.
  Bug 5: find_duplicates previously excluded same-seller rows entirely, making
         it impossible to report duplicate_same_seller.
         Fix: return ALL matching rows with a `same_seller` boolean flag.
         integration.py expects {found, same_seller}.
  Bug 6: Default threshold was 10; Nyakallo tuned 28 on the fixture set.
         Fix: default is now 28.
"""
import hashlib
import io
import os

import imagehash
from PIL import Image
from sqlalchemy.orm import Session

from app.db.models import Fingerprint

# Nyakallo's tuned threshold: copies ≤14 bits apart, different receipts ≥56.
# Configurable via env var.
HAMMING_THRESHOLD = int(os.getenv("PHASH_HAMMING_THRESHOLD", "28"))

# SQLite signed-int offset: shift uint64 into signed int64 range
_INT64_OFFSET = 2 ** 63


# ---------------------------------------------------------------------------
# Fingerprint computation
# ---------------------------------------------------------------------------

def compute_image_hash(raw: bytes) -> tuple[str, int]:
    """
    Compute a 64-bit perceptual hash of an image.
    Returns (hex_string, signed_int_for_sqlite).
    The signed int is stored as (uint64 - 2^63) to fit SQLite INTEGER.
    """
    img = Image.open(io.BytesIO(raw))
    ph = imagehash.phash(img)
    hex_str = str(ph)   # 16-char hex, used as source of truth
    # Convert boolean array → unsigned int → signed int for SQLite
    uint64 = int("".join("1" if b else "0" for b in ph.hash.flatten()), 2)
    signed = uint64 - _INT64_OFFSET
    return hex_str, signed


def compute_pdf_hash(raw: bytes) -> tuple[str, int]:
    """
    Normalised content hash for PDFs (SHA-256).
    Returns (hex_digest, signed_int_for_sqlite).
    """
    normalised = b" ".join(raw.split())
    digest = hashlib.sha256(normalised).hexdigest()
    uint64 = int(digest[:16], 16)
    signed = uint64 - _INT64_OFFSET
    return digest, signed


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def save_fingerprint(
    db: Session,
    seller_id: str,
    check_id: str,
    hash_hex: str,
    hash_int: int,
) -> Fingerprint:
    """Persist a fingerprint row linked to a seller and check."""
    fp = Fingerprint(
        seller_id=seller_id,
        check_id=check_id,
        hash=hash_hex,
        hash_int=hash_int,
    )
    db.add(fp)
    db.commit()
    db.refresh(fp)
    return fp


# ---------------------------------------------------------------------------
# Near-duplicate lookup
# ---------------------------------------------------------------------------

def find_duplicates(
    db: Session,
    hash_int: int,
    current_seller_id: str,
    threshold: int = HAMMING_THRESHOLD,
) -> list[dict]:
    """
    Return ALL fingerprints (any seller) within Hamming distance ≤ threshold.
    Each result includes a `same_seller` flag so the caller can distinguish:
      - same_seller=True  → duplicate_same_seller (WAIT)
      - same_seller=False → duplicate_image from another seller (STOP)

    This matches the dict shape integration.py expects:
      {"found": bool, "same_seller": bool}

    Only the hash and distance are returned — the other seller's identity
    is never exposed.
    """
    candidates = (
        db.query(Fingerprint)
        .filter(Fingerprint.hash_int.isnot(None))
        .all()
    )

    matches = []
    for fp in candidates:
        dist = _hamming(hash_int, fp.hash_int)
        if dist <= threshold:
            matches.append(
                {
                    "fingerprint_id": fp.id,
                    "check_id": fp.check_id,
                    "distance": dist,
                    "same_seller": fp.seller_id == current_seller_id,
                }
            )
    return matches


def dup_result(matches: list[dict]) -> dict:
    """
    Collapse match list into the {found, same_seller} dict that
    integration.py and the engine expect.
    Priority: cross-seller match > same-seller match > not found.
    """
    if not matches:
        return {"found": False, "same_seller": False}
    cross = [m for m in matches if not m["same_seller"]]
    if cross:
        return {"found": True, "same_seller": False}
    return {"found": True, "same_seller": True}


def _hamming(a: int, b: int) -> int:
    """Hamming distance between two signed integers stored in SQLite."""
    # Re-add offset to recover original bit patterns before XOR
    ua = (a + _INT64_OFFSET) & 0xFFFFFFFFFFFFFFFF
    ub = (b + _INT64_OFFSET) & 0xFFFFFFFFFFFFFFFF
    return bin(ua ^ ub).count("1")
