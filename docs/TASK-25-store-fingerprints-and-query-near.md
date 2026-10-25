---
title: "TASK-25: Store fingerprints and query near-duplicates from OTHER sellers"
labels: ["enhancement", "backend", "database"]
milestone: MVP
---
## Summary
Compute a fingerprint for each uploaded proof of payment, store it, and flag near-duplicates that were previously submitted by a **different** seller (a slip reused across sellers is a strong fraud signal).

## Requirements
- [x] Fingerprint function: 64-bit perceptual hash (`imagehash.phash`) for images; normalised SHA-256 for PDFs
- [x] Store the fingerprint in the `fingerprints` table linked to the seller and check
- [x] Query near-duplicates using Hamming distance at or below a configurable threshold
- [x] Exclude the current seller's own fingerprints — re-uploading your own slip is not a cross-seller match
- [x] Return match count in the verdict without exposing the other seller's identity or business name
- [x] Threshold configurable via `PHASH_HAMMING_THRESHOLD` env var (default `10`)

## Acceptance criteria
- [x] Same image from seller A then seller B → flagged for B (`tests/test_task25_fingerprints.py`)
- [x] Same image uploaded twice by seller A → not flagged
- [x] Slightly resized copy → still detected
- [x] Unrelated image → not flagged
- [x] Tests cover all four cases

## Implementation notes
- Module: `backend/app/db/fingerprints.py`
- `compute_image_hash(raw: bytes)` → `(hex_str, int_val)` using `imagehash.phash`
- `compute_pdf_hash(raw: bytes)` → `(hex_str, int_val)` using SHA-256 of normalised bytes
- `save_fingerprint(db, seller_id, check_id, hash_hex, hash_int)` → `Fingerprint`
- `find_duplicates(db, hash_int, current_seller_id, threshold)` → list of match dicts
- Hamming distance computed in Python; suitable for hackathon scale. For production, use a vector index.
- `hash_int` stored in the `fingerprints` table for fast in-process comparison

## Privacy
Only the hash is stored, never the raw file (see #26).

## Dependencies
Depends on #22 and #24.
