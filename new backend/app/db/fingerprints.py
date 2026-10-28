from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.db.models import Fingerprint

_INT64_OFFSET = 2**63


def compute_file_hash(raw: bytes) -> tuple[str, int, str]:
    digest = hashlib.sha256(raw).hexdigest()
    signed = int(digest[:16], 16) - _INT64_OFFSET
    return digest, signed, "sha256"


def save_fingerprint(
    db: Session,
    seller_id: str,
    check_id: str,
    hash_hex: str,
    hash_int: int | None,
    hash_algo: str = "sha256",
) -> Fingerprint:
    fingerprint = Fingerprint(
        seller_id=seller_id,
        check_id=check_id,
        hash=hash_hex,
        hash_int=hash_int,
        hash_algo=hash_algo,
    )
    db.add(fingerprint)
    db.flush()
    return fingerprint


def find_duplicates(
    db: Session,
    hash_hex: str,
    hash_algo: str,
    current_seller_id: str,
) -> list[dict]:
    candidates = (
        db.query(Fingerprint)
        .filter(Fingerprint.hash_algo == hash_algo, Fingerprint.hash == hash_hex)
        .all()
    )
    return [
        {
            "fingerprint_id": item.id,
            "check_id": item.check_id,
            "distance": 0,
            "same_seller": item.seller_id == current_seller_id,
        }
        for item in candidates
    ]


def dup_result(matches: list[dict]) -> dict:
    if not matches:
        return {"found": False, "same_seller": False}
    if any(not match["same_seller"] for match in matches):
        return {"found": True, "same_seller": False}
    return {"found": True, "same_seller": True}
