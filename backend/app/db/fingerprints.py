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


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def save_fingerprint(
    db: Session,
    seller_id: str,
    check_id: str,
    hash_hex: str,
    hash_int: int | None,
    hash_algo: str = "phash64",
) -> Fingerprint:
    fp = Fingerprint(
        seller_id=seller_id,
        check_id=check_id,
        hash=hash_hex,
        hash_int=hash_int,        # None for phash1024
        hash_algo=hash_algo,
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
    threshold: int | None = None,
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
    for fp in candidates:
        dist = _hamming(hash_hex, fp.hash, hash_algo)
        if dist <= threshold:
            matches.append({
                "fingerprint_id": fp.id,
                "check_id":       fp.check_id,
                "distance":       dist,
                "same_seller":    fp.seller_id == current_seller_id,
            })
    return matches


def dup_result(matches: list[dict]) -> dict:
    if not matches:
        return {"found": False, "same_seller": False}
    if any(not m["same_seller"] for m in matches):
        return {"found": True,  "same_seller": False}
    return     {"found": True,  "same_seller": True}


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