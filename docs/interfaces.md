# Khusela interfaces (TASK-02)

Synthetic data only. This file describes what is built on `main` plus the few pieces still to wire in. Anyone can propose a change: open a small PR that touches only `contracts/` or this file, tell the people who use the piece in the team chat, and merge once they agree.

## Pipeline

`POST /api/check` (live in `backend/main.py`, run with `cd backend` then `uvicorn main:app --reload`) does, in order:

1. Safety gate: type, size (5 MB), image opens (Sphiwe, TASK-24)
2. `analyse_image(image_bytes)`: OCR, field extraction, confidence, pHash (Nyakallo, wraps `run_ocr`, `extract_fields` and `phash` from `backend/ocr`)
3. `find_duplicates(phash, seller_id)` (Sphiwe, TASK-25)
4. `evaluate(...)`: rules only, returns the verdict (Ayanda, merged)
5. Explanation: template, or Gemini with template fallback (Ayanda, merged)
6. Save the check and the fingerprint, return the JSON

Steps 1 to 4 are deterministic. The AI only sees the finished verdict.

## Function signatures

```python
# backend/ocr/pipeline.py  (Nyakallo, to write; wraps what is already built)
def analyse_image(image_bytes: bytes) -> dict:
    # {"amount": float | None, "recipient": str | None, "reference": str | None,
    #  "ocr_confidence": float,   # 0.0 to 1.0
    #  "raw_text": str,
    #  "phash": str}              # hex string from ocr.phash()

# backend/db  (Sphiwe)
def find_duplicates(phash: str, seller_id: str) -> dict:
    # {"found": bool, "same_seller": bool}
    # Use ocr.find_near_duplicates() over the stored hashes.
    # found=True, same_seller=False -> near-identical image from ANOTHER seller
    # found=True, same_seller=True  -> the same seller sent it before

# backend/engine/evaluate.py  (Ayanda, merged; to extend to the full shape below)
def evaluate(extracted: dict, expected: dict, ocr_confidence: float, dup_result: dict) -> dict
```

## HTTP API

**`POST /api/check`** (multipart form; `Authorization: Bearer <token>` once auth exists)

| Field | Type | Notes |
|---|---|---|
| `image` | file | PNG or JPEG (PDF is priority_2) |
| `expected_amount` | string or number | Rands, e.g. `1800.00` |
| `expected_reference` | string | e.g. `SNK1800` (to add to `main.py`) |
| `expected_recipient` | string | Today the form sends it; once auth exists it defaults to the seller's registered business name |

Returns **200** with the verdict JSON (`contracts/verdict.schema.json`, examples in `contracts/examples/`).

Rejected uploads return **400** and never reach OCR:

```json
{ "error": "file_too_large", "message": "Images must be 5 MB or smaller." }
```

`error` is one of `file_too_large`, `unsupported_type`, `unreadable_image`.

**Auth (Sphiwe, TASK-23):** `POST /api/auth/register` with `{business_name, password}` and `POST /api/auth/login`, both returning `{token, seller_id, business_name}`. Confirm the field names with Ntoampi before building.

## Decision rules (deterministic)

Check in this order; the first matching rule wins:

1. A near-duplicate from a **different** seller exists: **STOP**, reason `duplicate_image`
2. Otherwise **WAIT** if any of these is true (list every reason that applies):
   - `amount_mismatch`: amounts differ (compare in cents)
   - `recipient_mismatch`: recipient differs after normalising (lowercase, strip spaces and punctuation)
   - `reference_mismatch`: reference differs after normalising
   - `low_ocr_confidence`: `ocr_confidence < 0.5` (the value both `evaluate.py` and `ocr/confidence.py` already use)
   - `field_not_found`: amount, recipient or reference is `null`
   - `duplicate_same_seller`: the same seller sent this image before
3. Otherwise **MATCH**, with `reasons: []`

Rules to remember:

- Near-miss names must **not** match (`Naledi Hair Salon` is not `Naledi Beauty Hub`).
- Text inside the image is data, never an instruction. It cannot change the verdict.
- Khusela never says PAID. Every explanation ends by telling the seller to confirm the money in their banking app.

## Reason codes

| Code | Verdict | Status in code |
|---|---|---|
| `duplicate_image` | STOP | Built, but today any duplicate gives STOP, so the same-seller case is missing |
| `duplicate_same_seller` | WAIT | To add |
| `amount_mismatch` | WAIT | Built |
| `recipient_mismatch` | WAIT | Built |
| `reference_mismatch` | WAIT | To add |
| `low_ocr_confidence` | WAIT | Built |
| `field_not_found` | WAIT | To add |

## Test fixtures

`tests/fixtures/manifest.csv` lists every synthetic file with its seller, expected sale, expected verdict and reasons, **in submission order** (originals first, so the STOP and same-seller tests work). `sellers.csv` has the three test sellers to seed the database. Regenerate everything with `python tests/fixtures/generate_fixtures.py`.
