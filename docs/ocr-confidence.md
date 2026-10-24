# OCR confidence and raw text

`run_ocr()` returns the raw text Tesseract produced and a reliability score on
the same `0.0–1.0` scale as the verdict contract:

```python
from ocr import run_ocr

result = run_ocr("screenshot.png")

print(result.raw_text)          # raw OCR text, contract key raw_ocr_text
print(result.confidence)        # 0.0 - 1.0, contract key ocr_confidence
print(result.confidence_label)  # "low", "medium" or "high"
print(result.is_reliable)       # confidence >= 0.5
print(result.word_count)
print(result.as_dict())
```

`result.as_dict()` is ready to merge into an API response:

```json
{
  "raw_ocr_text": "PAYMENT SENT\nAmount: R1,800.00\nTo: Thabo Sneakers\nReference: SNK1800",
  "ocr_confidence": 0.9389,
  "confidence_label": "high",
  "is_reliable": true,
  "word_count": 9,
  "mean_word_confidence": 0.9389,
  "low_confidence_ratio": 0.0,
  "backend": "local",
  "language": "eng",
  "psm": 6,
  "tesseract_version": "5.3.0",
  "preprocessed": true
}
```

The existing `result.text` and `result.confidence` attributes still work;
`raw_text` and `ocr_confidence` are the contract-friendly aliases.

## How the score is computed

Tesseract reports a confidence (0–100) for every word. A plain mean can look
healthy even when a blurry screenshot produces several garbage words, so the
score uses two signals:

```text
weighted_mean = Σ(word_confidence × word_length) / Σ(word_length)
low_ratio     = words_with_confidence < 0.5 / total_words
score         = weighted_mean × (1 - low_ratio)
```

- Longer words carry more weight than one-letter noise.
- Words below `LOW_CONFIDENCE_THRESHOLD` (0.5) reduce the final score.
- No recognised words gives `0.0`.
- The result is clamped to `0.0–1.0` and rounded to four decimals.

Labels use `0.5` and `0.75` as boundaries:

| Score | Label | Rule engine |
| --- | --- | --- |
| `< 0.5` | `low` | `WAIT` — image is too blurry to trust |
| `0.5 – 0.7499` | `medium` | usable, but verify carefully |
| `>= 0.75` | `high` | usable |

The rule engine already treats `ocr_confidence < 0.5` as unreadable, so the
thresholds line up.

### Why the penalty matters

On the synthetic screenshot in the test suite:

| Image | Score | Label | Recognised text |
| --- | --- | --- | --- |
| Sharp | `0.94` | high | `PAID R1,800.00 …` |
| Gaussian blur (radius 4) | `< 0.05` | low | mostly garbage or empty |

Averaging alone would leave moderately blurred screenshots in the `medium`
range even when several words are wrong. Penalising the low-confidence share
pushes genuinely unreadable images below `0.5`.

## Command line

```bash
# Full OCR output as JSON, including raw text and confidence
python backend/ocr/tesseract_engine.py --image screenshot.png --json

# Score an existing Tesseract TSV file
python backend/ocr/confidence.py --tsv out.tsv --json

# Pipe TSV on stdin
cat out.tsv | python backend/ocr/confidence.py --json
```

## Tests

Unit tests cover word weighting, the low-confidence penalty, empty output,
label boundaries and contract-shaped output:

```bash
python -m pytest backend/ocr/tests/test_confidence.py
```

The end-to-end test renders a sharp screenshot, blurs it, and checks that the
blurred image gets low confidence while the sharp one stays high:

```bash
KHUSELA_OCR_INTEGRATION=1 python -m pytest \
  backend/ocr/tests/test_confidence_integration.py
```

## Tuning

- If real screenshots are flagged `low`, inspect `mean_word_confidence` and
  `low_confidence_ratio` before changing the threshold.
- Improve the image first (see
  [ocr-preprocessing.md](ocr-preprocessing.md)); resizing small screenshots and
  thresholding usually raises confidence.
- If your Tesseract version gives systematically different word confidences,
  adjust `LOW_CONFIDENCE_THRESHOLD` in `backend/ocr/confidence.py` and update
  the tests.
- Confidence measures OCR reliability only. It does not prove the payment is
  genuine — the deterministic rule engine still owns the verdict.
