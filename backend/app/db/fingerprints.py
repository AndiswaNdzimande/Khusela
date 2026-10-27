"""
TASK-25: Fingerprint storage and near-duplicate lookup.

N1 fix (v5 report, CRITICAL):
  The previous version used imagehash (64-bit pHash) with a threshold of 28.
  Nyakallo's ocr module uses a 1024-bit DCT hash, and 28 was tuned for THAT
  hash. On a 64-bit hash, different receipts from the same template are only
  2-20 bits apart, so threshold 28 flagged 20 of 21 fixtures as duplicates.

  Fix: use ocr.phash (1024-bit hex string) and ocr.is_near_duplicate for
  comparison, exactly as docs/interfaces.md specifies. The hex string is stored
  in the existing `hash` column (String). hash_int is dropped from the lookup
  path (the column stays in the DB to avoid a migration, but is always NULL).

  Comparison is done in Python using ocr.is_near_duplicate(hex_a, hex_b).
  If the ocr module is unavailable (integration not yet merged), fall back to
  an exact-string match so the store stays safe rather than over-flagging.

Storage signatures match what integration.py expects:
  find_duplicates(phash_hex, seller_id)  → {"found": bool, "same_seller": bool}
  save_fingerprint(phash_hex, seller_id, check_id)
"""
import logging
import os

from sqlalchemy.orm import Session

from app.db.models import Fingerprint

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OCR hash bridge — use Nyakallo's 1024-bit hash functions if available
# ---------------------------------------------------------------------------

def _is_near_duplicate(hex_a: str, hex_b: str) -> bool:
    """
    Compare two pHash hex strings using ocr.is_near_duplicate when available.
    Falls back to exact-string comparison so the store never over-flags on
    a missing ocr module.
    """
    try:
        from ocr import is_near_duplicate  # backend/ocr module (Nyakallo)
        return is_near_duplicate(hex_a, hex_b)
    except ImportError:
        logger.warning(
            "ocr module not on sys.path — using exact-match fallback for duplicate check."
        )
        return hex_a == hex_b


def compute_phash(raw: bytes) -> str:
    """
    Compute the 1024-bit perceptual hash for an image using ocr.phash.
    Falls back to imagehash.phash (64-bit) only if ocr is unavailable,
    and logs a clear warning so it is visible in the startup log.
    """
    try:
        from ocr import phash  # backend/ocr module (Nyakallo)
        return phash(raw)
    except ImportError:
        logger.warning(
            "ocr module not on sys.path — using 64-bit imagehash fallback. "
            "Duplicate detection will be unreliable until integration is wired."
        )
        import io
        import imagehash
        from PIL import Image
        ph = imagehash.phash(Image.open(io.BytesIO(raw)))
        return str(ph)


# ---------------------------------------------------------------------------
# Storage  (signatures match docs/interfaces.md)
# ---------------------------------------------------------------------------

def save_fingerprint(
    db: Session,
    phash_hex: str,
    seller_id: str,
    check_id: str,
) -> Fingerprint:
    """
    Persist a fingerprint row.
    Args match the signature integration.py expects:
      save_fingerprint(phash_hex, seller_id, check_id)
    hash_int is left NULL — comparison is done on the hex string.
    """
    fp = Fingerprint(
        seller_id=seller_id,
        check_id=check_id,
        hash=phash_hex,
        hash_int=None,          # no longer used for comparison
    )
    db.add(fp)
    db.commit()
    db.refresh(fp)
    return fp


# ---------------------------------------------------------------------------
# Near-duplicate lookup  (signature matches docs/interfaces.md)
# ---------------------------------------------------------------------------

def find_duplicates(
    db: Session,
    phash_hex: str,
    current_seller_id: str,
) -> dict:
    """
    Compare phash_hex against every stored fingerprint using
    ocr.is_near_duplicate (1024-bit threshold).

    Returns {"found": bool, "same_seller": bool} where:
      found=True,  same_seller=False  → cross-seller duplicate → STOP
      found=True,  same_seller=True   → same-seller re-upload  → WAIT
      found=False                     → no duplicate
    """
    candidates = db.query(Fingerprint).all()

    cross_found = False
    same_found = False

    for fp in candidates:
        if not fp.hash:
            continue
        if _is_near_duplicate(phash_hex, fp.hash):
            if fp.seller_id == current_seller_id:
                same_found = True
            else:
                cross_found = True

    if cross_found:
        return {"found": True, "same_seller": False}
    if same_found:
        return {"found": True, "same_seller": True}
    return {"found": False, "same_seller": False}
