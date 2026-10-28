"""
TASK-25 (+ N1 fix): Fingerprint computation, storage and near-duplicate lookup.

Supports:
  * "phash1024" – Nyakallo's 1024-bit perceptual hash
  * "phash64"   – imagehash.phash fallback
  * "pdf_sha"   – normalised SHA-256 for PDFs

N1 fix (v5 report):
  * Adds `hash_algo` to Fingerprint rows.
  * `hash_int` is optional (None for 1024-bit hashes).
  * Hamming distance dispatches on `hash_algo`. Cross-algo = max distance.
  * Threshold is per-algorithm.
"""
import hashlib
import io
import logging
import os

import imagehash
from PIL import Image
from sqlalchemy.orm import Session

from app.db.models import Fingerprint

logger = logging.getLogger(__name__)

# --- Thresholds -------------------------------------------------------------
PHASH64_THRESHOLD   = int(os.getenv("PHASH_HAMMING_THRESHOLD", "28"))
PHASH1024_THRESHOLD = int(os.getenv("PHASH1024_HAMMING_THRESHOLD", "448"))
PDF_THRESHOLD       = int(os.getenv("PDF_HAMMING_THRESHOLD", "0"))

_THRESHOLDS = {
    "phash64":   PHASH64_THRESHOLD,
    "phash1024": PHASH1024_THRESHOLD,
    "pdf_sha":   PDF_THRESHOLD,
}

_INT64_OFFSET = 2 ** 63
_PHASH1024_HEX_LEN = 256   # 1024 bits / 4 bits per hex char


# ---------------------------------------------------------------------------
# Fingerprint computation
# ---------------------------------------------------------------------------

def _compute_phash1024(raw: bytes) -> str | None:
    """
    Try Nyakallo's 1024-bit hasher. Returns a 256-char lowercase hex string
    or None if the module is missing / returns something unexpected.
    """
    try:
        from engine.ocr.phash import compute_phash
    except ImportError:
        logger.info("engine.ocr.phash not importable — using phash64 fallback.")
        return None

    try:
        result = compute_phash(raw)
    except Exception as exc:
        logger.warning("compute_phash raised %s: %s — using phash64 fallback.",
                       type(exc).__name__, exc)
        return None

    hex_str = result if isinstance(result, str) else getattr(result, "hex", lambda: None)()
    if not isinstance(hex_str, str):
        logger.warning("compute_phash returned %s (not hex str) — using fallback.",
                       type(result).__name__)
        return None

    hex_str = hex_str.lower()
    if hex_str.startswith("0x"):
        hex_str = hex_str[2:]
    if len(hex_str) != _PHASH1024_HEX_LEN:
        logger.warning("compute_phash returned %d hex chars (expected %d) — using fallback.",
                       len(hex_str), _PHASH1024_HEX_LEN)
        return None
    return hex_str


def compute_image_hash(raw: bytes) -> tuple[str, int | None, str]:
    """
    Returns (hash_hex, hash_int_or_None, hash_algo).
    Prefers Nyakallo's 1024-bit hash; falls back to imagehash 64-bit.
    """
    hex_str = _compute_phash1024(raw)
    if hex_str is not None:
        return hex_str, None, "phash1024"

    # Fallback to 64-bit
    img = Image.open(io.BytesIO(raw))
    ph = imagehash.phash(img)
    hex_str = str(ph)              # 16-char hex
    uint64 = int(hex_str, 16)
    signed = uint64 - _INT64_OFFSET
    return hex_str, signed, "phash64"


def compute_pdf_hash(raw: bytes) -> tuple[str, int | None, str]:
    """Normalised SHA-256; exact-match only."""
    normalised = b" ".join(raw.split())
    digest = hashlib.sha256(normalised).hexdigest()
    uint64 = int(digest[:16], 16)
    signed = uint64 - _INT64_OFFSET
    return digest, signed, "pdf_sha"



def compute_reference_hash(
    reference: str | None,
    amount: float | None = None,
    timestamp: str | None = None,
) -> str | None:
    """
    Compute a normalised SHA-256 transaction key from reference, amount and timestamp.
    Used for reliable fraud duplicate detection across sellers.
    """
    if not reference:
        return None
    ref_norm = "".join(c for c in str(reference).lower() if c.isalnum())
    if not ref_norm:
        return None
    parts = [ref_norm]
    if amount is not None and amount > 0:
        parts.append(f"{amount:.2f}")
    if timestamp and str(timestamp).strip():
        parts.append(str(timestamp).strip())
    raw = ":".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def save_fingerprint(
    db: Session,
    seller_id: str,
    check_id: str,
    hash_hex: str,
<<<<<<< HEAD
    hash_int: int,
    reference_hash: str | None = None,
=======
    hash_int: int | None,
    hash_algo: str = "phash64",
>>>>>>> aba3f0e96c9b960aa272c9eec4807c3b8cc2fdaf
) -> Fingerprint:
    fp = Fingerprint(
        seller_id=seller_id,
        check_id=check_id,
        hash=hash_hex,
<<<<<<< HEAD
        hash_int=hash_int,
        reference_hash=reference_hash,
=======
        hash_int=hash_int,        # None for phash1024
        hash_algo=hash_algo,
>>>>>>> aba3f0e96c9b960aa272c9eec4807c3b8cc2fdaf
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
    hash_hex: str,
    hash_algo: str,
    current_seller_id: str,
<<<<<<< HEAD
    reference_hash: str | None = None,
    threshold: int = HAMMING_THRESHOLD,
=======
    threshold: int | None = None,
>>>>>>> aba3f0e96c9b960aa272c9eec4807c3b8cc2fdaf
) -> list[dict]:
    """
    Return ALL fingerprints (any seller) with the SAME hash_algo within
    Hamming distance ≤ threshold. Cross-algo comparison is never attempted.
    """
    if threshold is None:
        threshold = _THRESHOLDS.get(hash_algo, 0)

    candidates = (
        db.query(Fingerprint)
        .filter(Fingerprint.hash_algo == hash_algo)
        .filter(Fingerprint.hash.isnot(None))
        .all()
    )

    matches = []
<<<<<<< HEAD
    # 1. Primary duplicate signal: Reference / Transaction Hash match
    if reference_hash:
        ref_matches = (
            db.query(Fingerprint)
            .filter(Fingerprint.reference_hash == reference_hash)
            .all()
        )
        for fp in ref_matches:
            matches.append(
                {
                    "fingerprint_id": fp.id,
                    "check_id": fp.check_id,
                    "distance": 0,
                    "same_seller": fp.seller_id == current_seller_id,
                    "reason": "duplicate_reference",
                }
            )

    # 2. Secondary signal: pHash near-duplicate image match
    for fp in candidates:
        dist = _hamming(hash_int, fp.hash_int)
        if dist <= threshold:
            if not any(m["fingerprint_id"] == fp.id for m in matches):
                matches.append(
                    {
                        "fingerprint_id": fp.id,
                        "check_id": fp.check_id,
                        "distance": dist,
                        "same_seller": fp.seller_id == current_seller_id,
                        "reason": "duplicate_image",
                    }
                )
=======
    for fp in candidates:
        dist = _hamming(hash_hex, fp.hash, hash_algo)
        if dist <= threshold:
            matches.append({
                "fingerprint_id": fp.id,
                "check_id":       fp.check_id,
                "distance":       dist,
                "same_seller":    fp.seller_id == current_seller_id,
            })
>>>>>>> aba3f0e96c9b960aa272c9eec4807c3b8cc2fdaf
    return matches


def dup_result(matches: list[dict]) -> dict:
<<<<<<< HEAD
    """
    Collapse match list into the {found, same_seller, reason} dict that
    the engine expects.
    Priority: cross-seller match > same-seller match > not found.
    """
    if not matches:
        return {"found": False, "same_seller": False, "reason": None}
    cross = [m for m in matches if not m["same_seller"]]
    if cross:
        ref_match = next((m for m in cross if m.get("reason") == "duplicate_reference"), None)
        reason = "duplicate_reference" if ref_match else "duplicate_image"
        return {"found": True, "same_seller": False, "reason": reason}
    ref_match = next((m for m in matches if m.get("reason") == "duplicate_reference"), None)
    reason = "duplicate_reference" if ref_match else "duplicate_image"
    return {"found": True, "same_seller": True, "reason": reason}
=======
    if not matches:
        return {"found": False, "same_seller": False}
    if any(not m["same_seller"] for m in matches):
        return {"found": True,  "same_seller": False}
    return     {"found": True,  "same_seller": True}
>>>>>>> aba3f0e96c9b960aa272c9eec4807c3b8cc2fdaf


# ---------------------------------------------------------------------------
# Hamming distance
# ---------------------------------------------------------------------------

def _hamming(a_hex: str, b_hex: str, algo: str) -> int:
    """
    Bit-level Hamming distance between two hex hashes of the same algorithm.
    Different lengths → treated as maximally distant.
    pdf_sha → exact match only (0 or 256).
    """
    if algo == "pdf_sha":
        return 0 if a_hex == b_hex else 256

    if not a_hex or not b_hex or len(a_hex) != len(b_hex):
        return max(len(a_hex or ""), len(b_hex or "")) * 4

    try:
        return bin(int(a_hex, 16) ^ int(b_hex, 16)).count("1")
    except ValueError:
        return len(a_hex) * 4