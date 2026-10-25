---
title: "TASK-25: Store fingerprints and query near-duplicates from OTHER sellers"
labels: ["enhancement", "backend", "database"]
milestone: MVP
---
## Summary
Compute a fingerprint for each uploaded proof of payment, store it, and flag near-duplicates submitted by a **different** seller (a slip reused across sellers is a strong fraud signal).

## Requirements
- [x] Fingerprint function: 64-bit perceptual hash (`imagehash.phash`) for images; normalised SHA-256 for PDFs
- [x] Store the fingerprint in the `fingerprints` table linked to the seller and check
- [x] Query near-duplicates using Hamming distance at or below a configurable threshold
- [x] Return ALL matches with a `same_seller` flag — caller decides STOP (cross-seller) vs WAIT (same-seller)
- [x] Return match info without exposing the other seller's identity or business name
- [x] Threshold configurable via `PHASH_HAMMING_THRESHOLD` env var (default `28` — Nyakallo's tuned value)

## Bug fixes (v4 report)
- [x] **Bug 1 (CRITICAL):** pHash uint64 overflowed SQLite INTEGER (signed 64-bit max 2^63-1). Fixed by storing `value - 2^63` and adjusting Hamming XOR accordingly. `hash_int` column changed to `BigInteger`.
- [x] **Bug 5 (HIGH):** `find_duplicates` previously excluded same-seller rows entirely, making `duplicate_same_seller` impossible. Fixed: returns all matches with `same_seller` boolean flag.
- [x] **Bug 6 (MEDIUM):** Default threshold was 10; Nyakallo tuned 28 on fixtures. Fixed: default is now 28.

## Acceptance criteria
- [x] Same image from seller A then seller B → flagged, `same_seller=False`
- [x] Same image uploaded twice by seller A → flagged, `same_seller=True` (WAIT, not STOP)
- [x] Slightly resized copy → still detected
- [x] Unrelated image → not flagged
- [x] Tests cover all four cases + no OverflowError (`tests/test_task25_fingerprints.py`)

## Implementation notes
- Module: `backend/app/db/fingerprints.py`
- `compute_image_hash(raw)` → `(hex_str, signed_int)` — hex is source of truth, int for Hamming
- `find_duplicates(db, hash_int, current_seller_id)` → list of match dicts with `same_seller` flag
- `dup_result(matches)` → `{"found": bool, "same_seller": bool}` — shape `integration.py` expects

## Privacy
Only the hash is stored, never the raw file (see #26).

## Dependencies
Depends on #22 and #24.
