# Payment field extraction

`backend/ocr/extract.py` turns raw OCR text into the three fields the rule
engine needs:

```json
{
  "amount": 1800.0,
  "recipient": "Thabo Sneakers",
  "reference": "SNK1800"
}
```

The amount is a float in the same shape as
[`contracts/verdict.example.json`](../contracts/verdict.example.json). The
extractor is deterministic and rule-based; it does not call an LLM.

## Usage

```python
from ocr import extract_fields, run_ocr

ocr_result = run_ocr("screenshot.png")
fields = extract_fields(ocr_result.text)

print(fields.amount)       # 1800.0
print(fields.recipient)    # Thabo Sneakers
print(fields.reference)    # SNK1800 or None
print(fields.as_dict())    # contract-shaped dictionary
```

You can also extract from an image in one step:

```bash
python backend/ocr/extract.py --image screenshot.png
python backend/ocr/extract.py --image screenshot.png --json
python backend/ocr/extract.py --text "Paid R1,800.00 to Thabo Sneakers"
```

```json
{
  "amount": 1800.0,
  "recipient": "Thabo Sneakers",
  "reference": null
}
```

## Supported amount formats

| Input | Parsed |
| --- | --- |
| `R1,800.00` | `1800.0` |
| `R 1 800.00` | `1800.0` |
| `R1 800` | `1800.0` |
| `1800.00` | `1800.0` |
| `1 800,00` | `1800.0` |
| `1.800,00` | `1800.0` |
| `ZAR 2 450.50` | `2450.5` |

Amount selection is context-aware:

- Currency-marked amounts (`R`, `ZAR`) score highest.
- Labels such as `Amount`, `Total`, `Paid`, `Sent` and `Transferred` get a bonus.
- `Fee`, `Charge` and `Balance` are penalised.
- Values near `Reference`, `Phone`, `Account`, `Card` or `Date` are rejected.
- A bare `1800.00` is accepted, but bare integers such as years, phone numbers
  and reference IDs are ignored.
- Dates (`2026`), phone numbers (`082 123 4567`) and reference codes such as
  `1800.00` under a `Reference:` label do not become the amount.

## Recipient rules

Recipients are found on lines or sentences containing:

- `To:`, `Paid to`, `Payment to`, `Sent to`, `Transferred to`
- `Recipient` / `Recipient Name`
- `Beneficiary` / `Beneficiary Name`
- `Payee` / `Payee Name`
- Inline sentences such as `You paid R1,800.00 to Thabo Sneakers`

Values stop before trailing `Reference`, `Ref`, `Amount`, `Date`, `Bank`,
`Account` and similar labels. If the label is on its own line, the next
non-empty line is used. Original capitalisation (`THABO SNEAKERS`) is kept;
comparison happens later in the rule engine.

## Reference rules

References are found after labels such as:

- `Reference`, `Ref`, `Ref No`
- `Payment reference`, `Transaction reference`
- `Payment ID`, `Transaction ID`
- `Invoice No`, `Order No`

Internal spaces are removed (`SNK 1800` → `SNK1800`). Codes containing digits
and/or uppercase letters are kept. Missing references return `None`.

## Synthetic set

The synthetic OCR set lives in
[`tests/fixtures/synthetic/ocr_texts.json`](../tests/fixtures/synthetic/ocr_texts.json)
and covers Capitec/FNB/Standard Bank/TymeBank/Absa/Nedbank-style layouts,
spaced and comma amounts, next-line values, fees/balances, dates, phone numbers
and reference collisions.

```bash
# All cases run offline, no Tesseract needed
python -m pytest backend/ocr/tests/test_extract.py
```

End-to-end tests render light, dark-mode and degraded JPEG screenshots, run
Tesseract, then extract the fields:

```bash
KHUSELA_OCR_INTEGRATION=1 python -m pytest \
  backend/ocr/tests/test_extract_integration.py
```

## Limitations

- Handwritten receipts and very noisy OCR may still need manual review.
- Common OCR character confusions (`O`/`0`, `I`/`1`) are not corrected inside
  amounts yet; preprocessing normally removes them.
- If a screenshot contains multiple recipients, the highest-confidence label
  is returned.
- The extractor does not verify that money actually moved — that is the rule
  engine's job.
