# Khusela status (update after every merge)

Last updated: 24 Oct 2026

## Done on main
TASK-09 to 14 (engine), TASK-15 to 19 (OCR, pHash), TASK-02 contract (merged).

## In this branch (feat/TASK-05-integration)
- backend/integration.py: full pipeline with stand-ins
- backend/main.py: real pipeline, POST /check and /api/check, 400 for bad uploads, 503 if OCR missing, /api/demo/reset (demo only, remove before any real use)
- backend/tests/test_integration.py: 24 passing, 5 xfail

## Open engine gaps (owner: Ayanda, backend/engine/evaluate.py)
- reference_mismatch not checked (r01, r02)
- same-seller near-duplicate returns STOP; should be WAIT with duplicate_same_seller, and must not hide low_ocr_confidence (d01, b01, b02)
- field_not_found not implemented
- evaluate() returns its own shape; integration.py builds the contract shape around it

## Waiting on others
- Nyakallo: backend/ocr/pipeline.py analyse_image
- Sphiwe: fingerprint store (TASK-25), safety gate (TASK-24), auth (TASK-23)
- Ntoampi: frontend (TASK-28 onward)
- Andiswa: merge TASK-03 fixtures (tests/fixtures) so the integration tests run on main
