# Khusela status (update after every merge)

Last updated: 25 Oct 2026 (reconciled: repo zip + v3 status report + Team Start Guide)
Event: in person 27-28 Oct. Gates: hour 12 end to end (met, on stand-ins), hour 24 all three outcomes (partly met), hour 40 freeze (not started).

## Headline
- Core pipeline works on real screenshots: 17 of 22 testable fixtures match the manifest. The 5 failures are engine gaps (below).
- Frontend merged (PR #45, 25 Oct). Not run in this check; read from code only.
- CORRECTION to the v3 report: Sphiwe's backend IS in main. PR #46 (fc78f6e, 25 Oct) added TASK-21..27 under backend/app/ (auth, safety gate, models, fingerprints, scheduler, pdf sandbox). The v3 report looked in backend/api and backend/db, which only hold .gitkeep.
- BUT none of it is wired in. integration.py imports api.safety and db.fingerprints, which do not exist, so it silently uses the in-memory stand-ins. Confirmed: validate_upload, find_duplicates and analyse_image all load from integration.py itself.
- Two separate FastAPI apps now exist: backend/main.py (real pipeline, no auth, what the frontend can use) and backend/app/main.py (auth, JWT, SQLite, but its engine bridge is broken). Pick one.

## Test results (this check, fresh run)
- backend/engine/tests: 8 passed
- backend/ocr/tests: 98 passed, 6 skipped
- backend/tests/test_integration.py: 23 passed, 5 xfail (the 5 engine gaps)
- backend/tests (Sphiwe, test_task21..26): not trustworthy yet, see bugs below. Some failures were environment (my sandbox), the three below are real.
- Running "pytest" from the repo root fails to collect: backend/tests and backend/engine/tests are both a package called "tests". Run each folder separately or add __init__.py to backend/engine.

## Real bugs in Sphiwe's code (backend/app), found by reading and running
1. Fingerprint int overflow: compute_image_hash returns a 64-bit unsigned int; SQLite INTEGER is signed 63-bit. About half of all hashes crash on insert (OverflowError). Fix: store the hex string and compare in Python, or store signed (value - 2**63).
2. safety.py does "async for chunk in file" on an UploadFile, which has no __aiter__ in current Starlette (TypeError). Fix: read in chunks with await file.read(65536) and stop at 5 MB.
3. routers/check.py _run_engine is broken against the real engine: wrong kwarg (duplicate= vs dup_result=), "from engine import evaluate" gives the module not the function, treats the OCR result as a dict, hard-codes same_seller False, and only catches ImportError. It should call integration.check_payment instead.
4. Also: form field is "file" but the frontend sends "image"; auth routes are /auth/* but the frontend calls /api/auth/*; login takes business_name+password but the frontend sends a token; JWT_SECRET_KEY must be set or the app crashes at import; it stores raw images for 24h (the pitch says no stored images); responses use 413/415/422 but the contract says one 400 code; allows PDF but the contract says PNG/JPEG only.
5. Duplicate logic only returns OTHER sellers' matches, so same-seller repeat (d01) can never be reported as WAIT.
6. Hamming threshold 10 here vs 28 in Nyakallo's tuned pHash (backend/ocr). Use Nyakallo's.

## Tasks (36)
Done: 01, 02, 03, 09-14, 15-19, 28, 30-35.
Partial: 05 (built, PR not merged), 20, 29 (fake live login), 36 (no seller identity), 21-27 (merged in PR #46 but not integrated, bugs above, so treat as PARTIAL not unverified).
Not started: 04 WhatsApp mock (P2), 06 acceptance tests, 07 offline demo check, 08 pitch and backup video.

## Open engine gaps (Ayanda, backend/engine/evaluate.py)
- reference_mismatch never checked (r01, r02: a wrong reference still gives MATCH)
- same-seller repeat gives STOP, should be WAIT + duplicate_same_seller (d01)
- low_ocr_confidence hidden on blurry copies (b01, b02)
- field_not_found missing; amount parser disagrees with ocr.parse_amount ("R1 800,00" -> 180000); sign dropped; expected 0 + nothing read = MATCH
- STOP template says "known scam"; AI output not checked after generation

## Critical before demo
1. /api/demo/reset: FIXED on branch feat/TASK-05-integration (404 unless KHUSELA_DEMO_KEY is set, then needs X-Demo-Key header; 3 tests in backend/tests/test_demo_reset.py). Not yet merged to main.
2. Reference check (above).
3. Real seller identity from the token, not a form field. Until then cross-seller detection is not truly working.

## Next actions (in order)
1. Andiswa: reset endpoint locked (done in code). Push TASK-05 branch, open PR "Closes #5", Ayanda reviews.
2. Team decision (tonight): make backend/main.py the one app and bring Sphiwe's auth + SQLite store into it (move or re-export as backend/api/safety.py and backend/db/fingerprints.py so integration.py picks them up), with Sphiwe fixing bugs 1-3.
3. Ayanda: engine gaps; the 5 xfail tests turn green. Cover: Nyakallo.
4. Nyakallo: ocr/pipeline.py analyse_image; add Tesseract PATH step to docs/ocr-setup.md.
5. Ntoampi: align upload field name, auth routes and login body with the chosen API; clear history on sign-out; drop WebP.
6. Andiswa: write the 8 acceptance tests, offline check (Wi-Fi off), pitch script.
7. Log "using stand-in for X" at startup so a silent fallback cannot happen again.
8. Housekeeping: __pycache__/.idea/.pytest_cache are in the zip (check git ls-files), add .gitattributes (CRLF), close issues only via merged PRs, confirm vna-07 is Ayanda's second account.
