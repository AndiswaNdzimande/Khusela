"""Perceptual hashing (pHash) for near-duplicate payment screenshots.

pHash turns an image into a short hexadecimal fingerprint.  Two images with a
small Hamming distance between their fingerprints are visually similar, which
lets Khusela catch a screenshot that a scammer re-sent, resized or re-compressed
for a different order.

The implementation uses the classic DCT pHash algorithm:

1. Convert the image to grayscale.
2. Resize it to ``hash_size * highfreq_factor`` square.
3. Take a 2-D DCT and keep the low-frequency ``hash_size x hash_size`` block.
4. Set a bit when a coefficient is above the median coefficient.
5. Pack the bits into a hexadecimal string.

It deliberately uses NumPy only instead of adding OpenCV, SciPy or imagehash
as a dependency, so the same code runs on every team laptop without extra
binary or compiler setup.  The output is compatible with the DCT pHash used by
``imagehash`` when the same ``hash_size`` and ``highfreq_factor`` are used.

The default 32x32 (1024-bit) hash is intentionally larger than the usual 8x8
pHash.  Payment screenshots are mostly white space with small amounts of text;
a 64-bit hash can give two different amounts in the same template the same
hash.  The 1024-bit variant keeps enough detail to separate those while still
tolerating resizing, JPEG compression, brightness changes and light blurring.
``hash_size=8`` is available for a conventional 64-bit hash, but it is not
recommended for payment screenshots because different amounts in one template
can collide.

Thresholds are measured on the synthetic screenshot corpus in
``backend/ocr/tests/test_phash.py``.  With the default hash size, near
duplicates (resize/JPEG/brightness/contrast/light blur) score at most 26 bits
different, while different amounts, recipients and layouts score at least 32
bits apart.  ``DEFAULT_HAMMING_THRESHOLD`` is therefore 28.

Command line usage::

    python backend/ocr/phash.py --image screenshot.png --json
    python backend/ocr/phash.py --image a.png --compare b.png c.png
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping, Sequence, Union

import numpy as np
from PIL import Image

try:  # package import
    from .preprocess import ImageSource, load_image, to_grayscale
except ImportError:  # running as a plain script
    from preprocess import (  # type: ignore[no-redef]
        ImageSource,
        load_image,
        to_grayscale,
    )

HashLike = Union[str, int]
Candidate = Union[HashLike, tuple[str, HashLike]]
CandidateCollection = Union[Mapping[str, HashLike], Iterable[Candidate], HashLike]
LabeledPair = tuple[HashLike, HashLike, bool]

DEFAULT_HASH_SIZE = 32
DEFAULT_HIGHFREQ_FACTOR = 4
DEFAULT_HAMMING_THRESHOLD = 28


@dataclass(frozen=True)
class DuplicateMatch:
    """A candidate hash and its Hamming distance from the target."""

    key: str
    distance: int
    threshold: int = DEFAULT_HAMMING_THRESHOLD

    @property
    def is_duplicate(self) -> bool:
        return self.distance <= self.threshold

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "distance": self.distance,
            "threshold": self.threshold,
            "is_duplicate": self.is_duplicate,
        }


@dataclass(frozen=True)
class ThresholdReport:
    """Classification metrics for one Hamming-distance threshold."""

    threshold: int
    true_positives: int
    false_positives: int
    true_negatives: int
    false_negatives: int
    precision: float
    recall: float
    f1: float
    accuracy: float

    @property
    def total(self) -> int:
        return (
            self.true_positives
            + self.false_positives
            + self.true_negatives
            + self.false_negatives
        )

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _validate_hash_size(hash_size: int, highfreq_factor: int) -> None:
    if isinstance(hash_size, bool) or not isinstance(hash_size, int) or hash_size < 1:
        raise ValueError("hash_size must be a positive integer")
    if (
        isinstance(highfreq_factor, bool)
        or not isinstance(highfreq_factor, int)
        or highfreq_factor < 1
    ):
        raise ValueError("highfreq_factor must be a positive integer")


@lru_cache(maxsize=16)
def _dct_basis(size: int) -> np.ndarray:
    """Return the unnormalised DCT-II basis for a square image of ``size``."""
    positions = np.arange(size, dtype=np.float64)
    frequencies = positions.reshape(-1, 1)
    return np.cos(np.pi * (2.0 * positions + 1.0) * frequencies / (2.0 * size))


def _phash_bits(
    image: ImageSource,
    hash_size: int,
    highfreq_factor: int,
) -> np.ndarray:
    _validate_hash_size(hash_size, highfreq_factor)
    size = hash_size * highfreq_factor
    gray = to_grayscale(load_image(image))
    resized = gray.resize((size, size), Image.Resampling.LANCZOS)
    pixels = np.asarray(resized, dtype=np.float64)

    basis = _dct_basis(size)
    dct = basis @ pixels @ basis.T
    low_frequency = dct[:hash_size, :hash_size]

    # Normalise by the largest coefficient and discard floating-point noise.
    # Without this a uniform image can produce random bits from coefficients
    # that should be exactly zero, making blank screenshots unstable.
    largest = float(np.max(np.abs(low_frequency)))
    if largest > 0:
        low_frequency = low_frequency / largest
        low_frequency[np.abs(low_frequency) < 1e-12] = 0.0

    median = float(np.median(low_frequency))
    return low_frequency > median


def phash_int(
    image: ImageSource,
    *,
    hash_size: int = DEFAULT_HASH_SIZE,
    highfreq_factor: int = DEFAULT_HIGHFREQ_FACTOR,
) -> int:
    """Return the pHash as an integer."""
    bits = _phash_bits(image, hash_size, highfreq_factor).reshape(-1)
    packed = np.packbits(bits, bitorder="big").tobytes()
    return int.from_bytes(packed, "big")


def phash(
    image: ImageSource,
    *,
    hash_size: int = DEFAULT_HASH_SIZE,
    highfreq_factor: int = DEFAULT_HIGHFREQ_FACTOR,
) -> str:
    """Return the pHash as a fixed-width lowercase hexadecimal string.

    ``hash_size=8`` produces the conventional 64-bit (16 hex character) pHash.
    The default is 32 (1024 bits, 256 hex characters) for text-heavy payment
    screenshots.
    """
    _validate_hash_size(hash_size, highfreq_factor)
    bits = hash_size * hash_size
    width = (bits + 3) // 4
    value = phash_int(
        image,
        hash_size=hash_size,
        highfreq_factor=highfreq_factor,
    )
    return f"{value:0{width}x}"


def _coerce_hash(value: HashLike) -> tuple[int, int | None]:
    """Return ``(integer_value, bit_length)`` for a hash string or integer."""
    if isinstance(value, str):
        text = value.strip().lower()
        if text.startswith("0x"):
            text = text[2:]
        if not text:
            raise ValueError("hash must not be empty")
        if any(character not in "0123456789abcdef" for character in text):
            raise ValueError(f"invalid hexadecimal hash: {value!r}")
        return int(text, 16), len(text) * 4
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("hash must be a hexadecimal string or a non-negative integer")
    if value < 0:
        raise ValueError("hash integer must be non-negative")
    return value, None


def hamming_distance(hash_a: HashLike, hash_b: HashLike) -> int:
    """Count the number of differing bits between two pHashes.

    Hex strings must have the same length; otherwise the hashes were produced
    with different ``hash_size`` values and cannot be compared meaningfully.
    """
    value_a, bits_a = _coerce_hash(hash_a)
    value_b, bits_b = _coerce_hash(hash_b)
    if bits_a is not None and bits_b is not None and bits_a != bits_b:
        raise ValueError("hashes must have the same bit length")
    return (value_a ^ value_b).bit_count()


def _default_threshold_for_hash(value: HashLike) -> int:
    """Pick a sensible default threshold for the hash length.

    The tuned default (28) is for the 1024-bit screenshot hash.  A conventional
    64-bit hash needs a much smaller cut-off, otherwise nearly every pair looks
    like a duplicate.
    """
    _, bits = _coerce_hash(value)
    if bits is None:
        return DEFAULT_HAMMING_THRESHOLD
    if bits <= 256:
        return 5
    if bits <= 576:
        return 18
    if bits <= 1024:
        return DEFAULT_HAMMING_THRESHOLD
    return max(1, round(bits * DEFAULT_HAMMING_THRESHOLD / 1024))


def _resolve_threshold(
    threshold: int | None,
    reference_hash: HashLike,
) -> int:
    if threshold is None:
        return _default_threshold_for_hash(reference_hash)
    _validate_threshold(threshold)
    return threshold


def is_near_duplicate(
    hash_a: HashLike,
    hash_b: HashLike,
    threshold: int | None = None,
) -> bool:
    """Return ``True`` when two hashes are within the Hamming threshold.

    When ``threshold`` is omitted it is chosen from the hash length: 5 bits for
    a conventional 64-bit hash and 28 bits for the default 1024-bit hash.
    """
    distance = hamming_distance(hash_a, hash_b)
    resolved = _resolve_threshold(threshold, hash_a)
    return distance <= resolved


def _normalise_candidates(
    candidates: CandidateCollection,
) -> list[tuple[str, HashLike]]:
    if isinstance(candidates, Mapping):
        return [(str(key), value) for key, value in candidates.items()]
    if isinstance(candidates, (str, int)):
        return [(str(candidates), candidates)]

    normalised: list[tuple[str, HashLike]] = []
    for item in candidates:
        if isinstance(item, tuple) and len(item) == 2:
            key, value = item
            normalised.append((str(key), value))
        else:
            normalised.append((str(item), item))
    return normalised


def _validate_threshold(threshold: int, *, name: str = "threshold") -> None:
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, int)
        or threshold < 0
    ):
        raise ValueError(f"{name} must be a non-negative integer")


def find_near_duplicates(
    target_hash: HashLike,
    candidates: CandidateCollection,
    threshold: int | None = None,
    *,
    limit: int | None = None,
) -> list[DuplicateMatch]:
    """Find every candidate within ``threshold`` bits of ``target_hash``.

    ``candidates`` can be a mapping of ``key -> hash``, an iterable of
    ``(key, hash)`` pairs, or a single/iterable of hashes.  Results are sorted
    by distance and then key.  The target itself is not special-cased, so it
    will be returned when it is also present in ``candidates``.  When
    ``threshold`` is omitted it is inferred from the target hash length.
    """
    resolved = _resolve_threshold(threshold, target_hash)
    if limit is not None and (
        isinstance(limit, bool) or not isinstance(limit, int) or limit < 0
    ):
        raise ValueError("limit must be a non-negative integer or None")

    matches = [
        DuplicateMatch(
            key=key,
            distance=hamming_distance(target_hash, value),
            threshold=resolved,
        )
        for key, value in _normalise_candidates(candidates)
    ]
    matches = [match for match in matches if match.is_duplicate]
    matches.sort(key=lambda match: (match.distance, match.key))
    return matches if limit is None else matches[:limit]


def closest_match(
    target_hash: HashLike,
    candidates: CandidateCollection,
    threshold: int | None = None,
) -> DuplicateMatch | None:
    """Return the nearest candidate, even when it is not a duplicate."""
    resolved = _resolve_threshold(threshold, target_hash)
    normalised = _normalise_candidates(candidates)
    if not normalised:
        return None
    key, value = min(
        normalised,
        key=lambda item: (hamming_distance(target_hash, item[1]), item[0]),
    )
    return DuplicateMatch(
        key=key,
        distance=hamming_distance(target_hash, value),
        threshold=resolved,
    )


def _classification_counts(
    distances: Sequence[tuple[int, bool]],
    threshold: int,
) -> tuple[int, int, int, int]:
    true_positives = false_positives = true_negatives = false_negatives = 0
    for distance, expected_duplicate in distances:
        predicted_duplicate = distance <= threshold
        if expected_duplicate and predicted_duplicate:
            true_positives += 1
        elif expected_duplicate:
            false_negatives += 1
        elif predicted_duplicate:
            false_positives += 1
        else:
            true_negatives += 1
    return true_positives, false_positives, true_negatives, false_negatives


def _build_report(
    distances: Sequence[tuple[int, bool]],
    threshold: int,
) -> ThresholdReport:
    tp, fp, tn, fn = _classification_counts(distances, threshold)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (tp + tn) / len(distances)
    return ThresholdReport(
        threshold=threshold,
        true_positives=tp,
        false_positives=fp,
        true_negatives=tn,
        false_negatives=fn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        accuracy=round(accuracy, 4),
    )


def evaluate_threshold(pairs: Iterable[LabeledPair], threshold: int) -> ThresholdReport:
    """Score a threshold against labelled ``(hash_a, hash_b, duplicate)`` pairs."""
    _validate_threshold(threshold)
    distances = [
        (hamming_distance(hash_a, hash_b), bool(expected_duplicate))
        for hash_a, hash_b, expected_duplicate in pairs
    ]
    if not distances:
        raise ValueError("pairs must contain at least one labelled pair")
    return _build_report(distances, threshold)


def _fbeta(report: ThresholdReport, beta: float) -> float:
    beta_squared = beta * beta
    denominator = beta_squared * report.precision + report.recall
    if denominator == 0:
        return 0.0
    return (
        (1.0 + beta_squared)
        * report.precision
        * report.recall
        / denominator
    )


def tune_threshold(
    pairs: Iterable[LabeledPair],
    *,
    beta: float = 0.5,
    max_distance: int | None = None,
) -> ThresholdReport:
    """Choose the best Hamming threshold from labelled pairs.

    ``beta=0.5`` weights precision higher than recall.  For Khusela it is worse
    to call a genuine, different screenshot a duplicate than to miss a
    borderline near-duplicate, so the default favours precision.  When the
    classes are separable, the returned threshold sits near the midpoint of the
    gap between the largest duplicate distance and the smallest different
    distance, giving both sides as much room as possible.
    """
    if not isinstance(beta, (int, float)) or isinstance(beta, bool) or beta <= 0:
        raise ValueError("beta must be greater than zero")

    distances = [
        (hamming_distance(hash_a, hash_b), bool(expected_duplicate))
        for hash_a, hash_b, expected_duplicate in pairs
    ]
    if not distances:
        raise ValueError("pairs must contain at least one labelled pair")

    upper = max_distance
    if upper is None:
        upper = max(distance for distance, _ in distances)
    _validate_threshold(upper, name="max_distance")

    # Build the reports directly to avoid recomputing distances for every
    # threshold (the pair list may come from a generator).
    reports = [
        _build_report(distances, threshold) for threshold in range(upper + 1)
    ]
    best_score = max(_fbeta(report, beta) for report in reports)
    candidates = [
        report for report in reports if _fbeta(report, beta) == best_score
    ]

    positive_distances = [distance for distance, duplicate in distances if duplicate]
    negative_distances = [
        distance for distance, duplicate in distances if not duplicate
    ]
    if (
        positive_distances
        and negative_distances
        and max(positive_distances) < min(negative_distances)
    ):
        # The classes are separable.  Pick the middle of the valid interval
        # instead of hugging one edge of it.
        ideal = (max(positive_distances) + min(negative_distances) - 1) // 2
        return min(
            candidates,
            key=lambda report: (abs(report.threshold - ideal), report.threshold),
        )

    # Overlapping classes: the F-beta score already chose the best trade-off.
    # Break ties in favour of fewer false positives and then a stricter limit.
    return min(
        candidates,
        key=lambda report: (report.false_positives, report.threshold),
    )


def tune_threshold_from_file(
    labels_path: str | Path,
    *,
    hash_size: int = DEFAULT_HASH_SIZE,
    highfreq_factor: int = DEFAULT_HIGHFREQ_FACTOR,
    beta: float = 0.5,
) -> ThresholdReport:
    """Tune a threshold from a JSON labels file.

    The file contains a list of objects with ``a``, ``b`` and ``duplicate``
    keys.  Image paths are resolved relative to the labels file.  Example::

        [
          {"a": "original.png", "b": "resent.jpg", "duplicate": true},
          {"a": "original.png", "b": "other.png", "duplicate": false}
        ]
    """
    path = Path(labels_path)
    entries = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        raise ValueError("labels file must contain a JSON list")

    pairs: list[LabeledPair] = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"entry {index} must be a JSON object")
        try:
            image_a = entry["a"]
            image_b = entry["b"]
            duplicate = entry["duplicate"]
        except KeyError as exc:
            raise ValueError(f"entry {index} is missing {exc.args[0]!r}") from exc
        if not isinstance(duplicate, bool):
            raise ValueError(f"entry {index} duplicate must be true or false")
        pairs.append(
            (
                phash(
                    path.parent / str(image_a),
                    hash_size=hash_size,
                    highfreq_factor=highfreq_factor,
                ),
                phash(
                    path.parent / str(image_b),
                    hash_size=hash_size,
                    highfreq_factor=highfreq_factor,
                ),
                duplicate,
            )
        )
    return tune_threshold(pairs, beta=beta)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compute pHashes and compare payment screenshots"
    )
    parser.add_argument("--image", help="target image path")
    parser.add_argument(
        "--compare",
        nargs="+",
        metavar="IMAGE",
        help="other images to compare against the target",
    )
    parser.add_argument(
        "--tune",
        metavar="LABELS.json",
        help="tune the threshold from labelled image pairs",
    )
    parser.add_argument("--beta", type=float, default=0.5)
    parser.add_argument("--hash-size", type=int, default=DEFAULT_HASH_SIZE)
    parser.add_argument(
        "--highfreq-factor", type=int, default=DEFAULT_HIGHFREQ_FACTOR
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=None,
        help="Hamming cut-off (default: inferred from the hash size)",
    )
    parser.add_argument("--json", action="store_true", help="print JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.image and not args.tune:
        parser.error("--image is required unless --tune is used")
    try:
        if args.tune:
            if args.threshold is not None:
                _validate_threshold(args.threshold)
            report = tune_threshold_from_file(
                args.tune,
                hash_size=args.hash_size,
                highfreq_factor=args.highfreq_factor,
                beta=args.beta,
            )
            if args.json:
                print(json.dumps(report.as_dict(), indent=2))
            else:
                print(f"Recommended threshold: {report.threshold} bits")
                print(
                    f"TP={report.true_positives} FP={report.false_positives} "
                    f"TN={report.true_negatives} FN={report.false_negatives}"
                )
                print(
                    f"precision={report.precision:.4f} "
                    f"recall={report.recall:.4f} "
                    f"f1={report.f1:.4f} "
                    f"accuracy={report.accuracy:.4f}"
                )
            return 0

        target_hash = phash(
            args.image,
            hash_size=args.hash_size,
            highfreq_factor=args.highfreq_factor,
        )
        threshold = _resolve_threshold(args.threshold, target_hash)
        summary: dict[str, object] = {
            "image": str(args.image),
            "hash": target_hash,
            "hash_size": args.hash_size,
            "bits": args.hash_size * args.hash_size,
            "threshold": threshold,
        }

        matches: list[dict[str, object]] = []
        if args.compare:
            for path in args.compare:
                candidate_hash = phash(
                    path,
                    hash_size=args.hash_size,
                    highfreq_factor=args.highfreq_factor,
                )
                distance = hamming_distance(target_hash, candidate_hash)
                matches.append(
                    {
                        "image": str(path),
                        "hash": candidate_hash,
                        "distance": distance,
                        "is_duplicate": distance <= threshold,
                    }
                )
            summary["matches"] = matches

        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print(f"Image: {summary['image']}")
            print(f"pHash: {summary['hash']}")
            print(
                f"Hash size: {summary['hash_size']}x{summary['hash_size']} "
                f"({summary['bits']} bits)"
            )
            if args.compare:
                print(f"Threshold: {threshold} bits")
                for match in matches:
                    verdict = "DUPLICATE" if match["is_duplicate"] else "different"
                    print(
                        f"  {match['image']}: {match['distance']} bits "
                        f"({verdict})"
                    )
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
