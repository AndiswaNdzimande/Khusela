---
title: "TASK-25: Store fingerprints and query near-duplicates from OTHER sellers"
labels: ["enhancement", "backend", "database"]
milestone: MVP
---
## Summary
Compute a fingerprint for each uploaded proof of payment, store it, and flag near-duplicates that were previously submitted by a **different** seller (a slip reused across sellers is a strong fraud signal).

## Requirements
- [ ] Fingerprint function: perceptual hash for images; normalised text hash for PDFs
- [ ] Store the fingerprint in the `fingerprints` table linked to the seller and check
- [ ] Query near-duplicates using Hamming distance below a configurable threshold
- [ ] Exclude the current seller's own fingerprints (re-uploading your own slip is not a cross-seller match)
- [ ] Return matches in the verdict reasons without exposing the other seller's identity or business name
- [ ] Threshold configurable via environment variable, with a documented default

## Acceptance criteria
- [ ] Same image from seller A then seller B is flagged for B
- [ ] Same image uploaded twice by seller A is not flagged
- [ ] A slightly resized or recompressed copy is still detected
- [ ] An unrelated image is not flagged
- [ ] Tests cover all four cases

## Privacy
Only the hash is stored, never the raw file (see #26).

## Dependencies
Depends on #22 and #24.
