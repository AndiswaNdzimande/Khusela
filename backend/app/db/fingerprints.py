"""
TASK-25: Fingerprint computation, storage and near-duplicate lookup.

Images  → perceptual hash (pHash via imagehash)
PDFs    → normalised SHA-256 text hash (placeholder until TASK-27 sandbox is wired)

Near-duplicate detection uses Hamming distance on the integer representation of the hash.
Only matches from a DIFFERENT seller are returned (cross-seller fraud signal).
The current seller's own re-uploads are explicitly excluded.
"""
import hashlib
import io
import os

import imagehash
from PIL import Image
from sqlalchemy.orm import Session

from app.db.models import Fingerprint

# Hamming distance threshold – matches within this distance are flagged.
# Configurable via environment variable; default 10 (tight for 64-bit pHash).
HAMMING_THRESHOLD = int(os.getenv("PHASH_HAMMING_THRESHOLD", "10"))


# ---------------------------------------------------------------------------
# Fingerprint computation
# ---------------------------------------------------------------------------

def compute_image_hash(raw: bytes) -> tuple[str, int]:
    """
    Compute a 64-bit perceptual hash of an image.
    Returns (hex_string, integer_value).
    """
    img = Image.open(io.BytesIO(raw))
    ph = imagehash.phash(img)          # 64-bit pHash
    hex_str = str(ph)                  # 16-char hex string
    int_val = ph.hash.flatten().tolist()
    # Convert the boolean array to an integer for fast Hamming arithmetic
    int_val = int("".join("1" if b else "0" for b in ph.hash.flatten()), 2)
    return hex_str, int_val


def compute_pdf_hash(raw: bytes) -> tuple[str, int]:
    """
    Normalised content hash for PDFs.
    Strips whitespace variations and computes SHA-256.
    Full text extraction is deferred to the Docker sandbox (TASK-27).
    """
    normalised = b" ".join(raw.split())
    digest = hashlib.sha256(normalised).hexdigest()
    # Use first 16 hex chars (64 bits) as int for consistency with pHash
    int_val = int(digest[:16], 16)
    return digest, int_val


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
    Return fingerprints from OTHER sellers whose Hamming distance to hash_int
    is at or below the threshold.

    The current seller's own fingerprints are excluded so that re-uploading
    your own slip is never flagged as cross-seller fraud.

    Returns a list of dicts with keys: fingerprint_id, check_id, distance.
    The other seller's identity is intentionally NOT included.
    """
    # Pull all fingerprints except the current seller's own rows.
    # SQLite has no native bit-count function, so we filter in Python.
    # For a production system with large volumes, store the hash in a
    # dedicated ANN index (e.g. pgvector or FAISS).
    candidates = (
        db.query(Fingerprint)
        .filter(Fingerprint.seller_id != current_seller_id)
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
                }
            )
    return matches


def _hamming(a: int, b: int) -> int:
    """Count differing bits between two integers (Hamming distance)."""
    return bin(a ^ b).count("1")
