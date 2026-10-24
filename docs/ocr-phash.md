# Perceptual hashing and near-duplicate screenshots

`backend/ocr/phash.py` turns a payment screenshot into a perceptual hash
(pHash). A scammer who re-sends, resizes or re-compresses the same screenshot
gets a hash with a small **Hamming distance** from the original. A different
payment gets a much larger distance.

The implementation is pure Pillow + NumPy. It does not require OpenCV, SciPy or
the `imagehash` package, so the same code runs on every team laptop without
extra binary or compiler setup. It uses the same DCT pHash construction as
`imagehash` when given the same `hash_size` and `highfreq_factor`.

## Quick start

```python
from ocr import hamming_distance, is_near_duplicate, phash

original = phash("original.png")
received = phash("received.png")

distance = hamming_distance(original, received)
print(distance)
print(is_near_duplicate(original, received))
```

`phash()` accepts a path, `bytes`, a binary file object or a PIL image. The
result is a lowercase hexadecimal string. The default is a 32x32 (1024-bit,
256-character) hash:

```python
from ocr.phash import DEFAULT_HAMMING_THRESHOLD, DEFAULT_HASH_SIZE

assert DEFAULT_HASH_SIZE == 32
assert DEFAULT_HAMMING_THRESHOLD == 28
```

For a conventional 64-bit pHash, pass `hash_size=8`:

```python
hash_64 = phash("screenshot.png", hash_size=8)
```

That returns 16 hexadecimal characters. The matching conventional threshold is
about 5 bits, not 28; the threshold scales with the number of hash bits.
`is_near_duplicate()` and `find_near_duplicates()` infer the appropriate
threshold from the hash length when you omit it (5 for 64-bit, 28 for the
default 1024-bit hash). The 64-bit variant is useful for compatibility with
other tools, but it is not recommended for payment screenshots: in the
synthetic corpus it gives different amounts in the same template the same hash.

## How the hash is built

1. Flatten transparency and convert to grayscale.
2. Resize to `hash_size × highfreq_factor` square (128×128 by default).
3. Run a 2-D DCT.
4. Keep the low-frequency `hash_size × hash_size` block.
5. Set each bit when its coefficient is above the median coefficient.
6. Pack the bits into a hexadecimal string.

The larger-than-usual 32×32 block is deliberate. Payment screenshots contain a
lot of white space and only a few lines of text; a 64-bit pHash often gives two
different amounts in the same bank template the same fingerprint. The
1024-bit hash keeps enough detail to separate them while still tolerating
normal screenshot processing.

## Threshold tuning

The default threshold is **28 differing bits out of 1024**. It was measured on
the synthetic screenshot corpus in
`backend/ocr/tests/test_phash.py`:

| Change from the original | Hamming distance |
| --- | ---: |
| Resize to 60% | 8 |
| Resize to 25% | 14 |
| JPEG quality 20 | 12 |
| JPEG quality 5 | 18 |
| Brightness ×1.15 | 6 |
| Brightness ×0.85 | 26 |
| Contrast ×0.85 | 6 |
| Gaussian blur, radius 0.8 | 6 |
| Resize + brightness + JPEG (typical) | 10 |
| Resize + strong brightness + JPEG (heavy) | 34 |
| Different amount (`R1,800` → `R1,900`) | 34 |
| Different amount (`R1,800` → `R2,450.50`) | 92 |
| Different reference | 64 |
| Different recipient | 92 |
| Different bank layout | 134 |
| Dark-mode version of the same text | 1000 |

The observed near-duplicate maximum is 26 (a strong darkening) and the nearest
different image is at least 32 (font rendering can vary), so 28 sits in the gap
and still leaves a small margin.
The heavy combination of resizing, strong darkening and low-quality JPEG
(distance 34 in the table) is beyond the default and is intentionally left for
a future similarity review; raising the threshold toward 34 would start
flagging different amounts.

To tune the threshold against your own labelled screenshots:

```python
from ocr.phash import hamming_distance, phash, tune_threshold

pairs = [
    # (image_a, image_b, is_duplicate)
    ("original.png", "resent.jpg", True),
    ("original.png", "other_payment.png", False),
    # ...
]
labelled = [
    (phash(image_a), phash(image_b), duplicate)
    for image_a, image_b, duplicate in pairs
]

report = tune_threshold(labelled)
print(report.threshold)        # chosen cut-off
print(report.precision)
print(report.recall)
print(report.false_positives)
```

`tune_threshold()` uses an F0.5 score, which weights precision higher than
recall: wrongly calling a genuine, different screenshot a duplicate is worse
than asking a seller to review a borderline match. If the two classes are
separable, it picks the middle of the gap rather than hugging one edge.

`evaluate_threshold(labelled, threshold)` returns the same metrics for a
specific threshold:

```python
from ocr.phash import evaluate_threshold

report = evaluate_threshold(labelled, threshold=28)
print(report.as_dict())
```

## Finding matches in a collection

```python
from ocr.phash import find_near_duplicates

stored = {
    "order-101": phash("order-101.png"),
    "order-102": phash("order-102.png"),
    "order-103": phash("order-103.png"),
}
matches = find_near_duplicates(phash("received.png"), stored)
if matches:
    best = matches[0]
    print(best.key, best.distance, best.is_duplicate)
```

`candidates` can be a mapping, an iterable of `(key, hash)` pairs, or a list of
hashes. Results are sorted by distance and then key. `closest_match()` returns
the nearest candidate even when it is outside the threshold, which is useful
for a “similar images” review screen.

For a large fingerprint store, do not scan every row in Python. Store the hash
as text and either:

- bucket candidates by a fixed set of hash prefixes (for example the first 8
  nibbles) before computing full Hamming distances; or
- move the XOR + `bit_count()` comparison into the database if the database
  supports bit operations.

The current API is deliberately storage-agnostic so the fingerprint store task
can choose either approach.

## Command line

```bash
# Print the hash as JSON
python backend/ocr/phash.py --image screenshot.png --json

# Compare one image with several others
python backend/ocr/phash.py \
  --image original.png \
  --compare resent.jpg other_payment.png \
  --threshold 28

# Tune against a labelled corpus
python backend/ocr/phash.py --tune labels.json --json
```

The text output marks each comparison as `DUPLICATE` or `different`; `--json`
is suitable for scripts. If `--threshold` is omitted it is inferred from the
selected `--hash-size`.

`labels.json` is a list; paths are resolved relative to the labels file:

```json
[
  {"a": "original.png", "b": "resent.jpg", "duplicate": true},
  {"a": "original.png", "b": "other_payment.png", "duplicate": false}
]
```

## Tests

The unit tests build synthetic payment screenshots and verify resizing, JPEG
compression, brightness/contrast changes and light blur are detected, while
different amounts, recipients, references and bank layouts are not:

```bash
python -m pytest backend/ocr/tests/test_phash.py
```

They also cover Hamming-distance edge cases, invalid hashes, candidate
searching, threshold evaluation and the command line.

## Limitations

- pHash is not a cryptographic hash. It describes visual structure, not
  authenticity, and cannot prove a screenshot is genuine.
- It ignores colour and metadata. Two different-colour screenshots with the
  same layout can collide; the rule engine and OCR fields still do the
  substantive checks.
- Large geometric changes (cropping, rotation, a 2-pixel shift in the synthetic
  corpus) and very small text edits can fall outside the threshold. Near
  duplicates are expected to be copies that were resized, re-encoded or
  brightness-adjusted, not re-laid-out.
- Distances depend on how the screenshot renders text. In some fonts a
  one-digit amount change can score as close as a heavily compressed copy.
  Use pHash as a duplicate-candidate filter; the OCR amount/recipient/reference
  comparison remains the authoritative check.
- Blank or almost uniform images have little structure and should not be
  treated as meaningful duplicate evidence.
- Store the full hex string, not a truncated prefix, unless the prefix is only
  used as a bucketing key before the full comparison.
