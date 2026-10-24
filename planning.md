# Khusela planning

Goal: a seller uploads a payment screenshot plus the expected sale and gets STOP, WAIT or MATCH with a plain explanation. Python rules decide; the AI only explains. Demo must run on localhost with Wi-Fi off.

Gates: hour 12 one screenshot end to end, hour 24 all three outcomes, hour 40 code freeze.

## Pipeline (TASK-05, backend/integration.py)

safety gate -> analyse_image -> find_duplicates -> evaluate -> explanation -> save fingerprint -> verdict JSON

Each piece that belongs to someone else has a stand-in that is used only when the real module cannot be imported:

| Piece | Real module | Owner | Stand-in today |
|---|---|---|---|
| analyse_image(image_bytes) | backend/ocr/pipeline.py | Nyakallo | integration._standin_analyse_image |
| find_duplicates / save_fingerprint | backend/db/fingerprints.py | Sphiwe (TASK-25) | in-memory list |
| validate_upload | backend/api/safety.py | Sphiwe (TASK-24) | PIL check, 5 MB cap |

If a real module uses a different file or function name, change the single import line in integration.py.

## Phases

1. Understand: read contract (contracts/verdict.schema.json) and docs/interfaces.md. Done.
2. Build glue and slim main.py. Done.
3. Test: every fixture in tests/fixtures/manifest.csv through the pipeline. Done (backend/tests/test_integration.py).
4. Swap stand-ins for real modules as they merge. Waiting on Nyakallo and Sphiwe.
5. Engine gaps (Ayanda): reference_mismatch, field_not_found, same-seller handling. Tests marked xfail turn green when fixed.
6. Acceptance tests (TASK-06), offline demo check (TASK-07), pitch (TASK-08).
