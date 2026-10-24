"""Turn Tesseract TSV output into text plus a reliability score.

Tesseract reports a confidence (0-100) for every word. A plain mean can look
healthy even when a blurry screenshot produces several garbage words, so the
score here combines two signals:

* the mean word confidence, weighted by word length, and
* the share of words below :data:`LOW_CONFIDENCE_THRESHOLD`.

``score = weighted_mean * (1 - low_confidence_ratio)``

A sharp screenshot with no low-confidence words keeps its mean (~0.95). A blurry
screenshot with half its words below 50% is halved. The returned score is on the
same 0.0-1.0 scale as ``contracts/verdict.example.json``.

Command line usage::

    python backend/ocr/confidence.py --tsv out.tsv
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any

#: Words below this confidence (0.0-1.0) count towards the low-confidence ratio.
LOW_CONFIDENCE_THRESHOLD = 0.5

#: Scores below this are treated as unreadable by the rule engine.
RELIABLE_CONFIDENCE_THRESHOLD = 0.5

LineKey = tuple[str, str, str, str]


@dataclass(frozen=True)
class ConfidenceScore:
    """OCR reliability details for one image."""

    score: float
    mean_word_confidence: float
    low_confidence_ratio: float
    word_count: int

    @property
    def label(self) -> str:
        return confidence_label(self.score)

    @property
    def is_reliable(self) -> bool:
        return self.score >= RELIABLE_CONFIDENCE_THRESHOLD

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["label"] = self.label
        payload["is_reliable"] = self.is_reliable
        return payload


def confidence_label(score: float) -> str:
    """Return ``low``, ``medium`` or ``high`` for a 0.0-1.0 score."""
    if score < RELIABLE_CONFIDENCE_THRESHOLD:
        return "low"
    if score < 0.75:
        return "medium"
    return "high"


def compute_confidence(tsv: str) -> ConfidenceScore:
    """Compute a reliability score from Tesseract TSV output."""
    words: list[tuple[str, float]] = []

    reader = csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE)
    for row in reader:
        if str(row.get("level", "")).strip() != "5":
            continue
        word = (row.get("text") or "").strip()
        if not word:
            continue

        raw_conf = row.get("conf")
        try:
            conf = float(raw_conf)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if conf < 0:
            continue
        words.append((word, max(0.0, min(1.0, conf / 100.0))))

    if not words:
        return ConfidenceScore(
            score=0.0,
            mean_word_confidence=0.0,
            low_confidence_ratio=0.0,
            word_count=0,
        )

    total_weight = sum(max(1, len(word)) for word, _ in words)
    weighted_sum = sum(
        confidence * max(1, len(word)) for word, confidence in words
    )
    mean = weighted_sum / total_weight

    low_count = sum(
        1 for _, confidence in words if confidence < LOW_CONFIDENCE_THRESHOLD
    )
    low_ratio = low_count / len(words)

    score = max(0.0, min(1.0, mean * (1.0 - low_ratio)))

    return ConfidenceScore(
        score=round(score, 4),
        mean_word_confidence=round(mean, 4),
        low_confidence_ratio=round(low_ratio, 4),
        word_count=len(words),
    )


def parse_tsv(tsv: str) -> tuple[str, ConfidenceScore]:
    """Reconstruct text and confidence from Tesseract TSV output.

    Words are grouped into their original lines. Empty rows and rows with a
    confidence of ``-1`` are ignored for scoring but still contribute text when
    present.
    """
    lines: dict[LineKey, list[str]] = {}
    order: list[LineKey] = []

    reader = csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE)
    for row in reader:
        if str(row.get("level", "")).strip() != "5":
            continue
        word = (row.get("text") or "").strip()
        if not word:
            continue

        key = (
            str(row.get("page_num", "")),
            str(row.get("block_num", "")),
            str(row.get("par_num", "")),
            str(row.get("line_num", "")),
        )
        if key not in lines:
            lines[key] = []
            order.append(key)
        lines[key].append(word)

    text = "\n".join(" ".join(lines[key]) for key in order)
    return text, compute_confidence(tsv)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute an OCR confidence score from Tesseract TSV"
    )
    parser.add_argument("--tsv", help="path to a Tesseract TSV file (default: stdin)")
    parser.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)

    try:
        if args.tsv:
            tsv = open(args.tsv, encoding="utf-8", errors="replace").read()
        else:
            tsv = sys.stdin.read()
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    text, score = parse_tsv(tsv)
    if args.json:
        print(
            json.dumps(
                {"raw_ocr_text": text, **score.as_dict()},
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(f"Score:       {score.score:.2f} ({score.label})")
        print(f"Words:       {score.word_count}")
        print(f"Mean word:   {score.mean_word_confidence:.2f}")
        print(f"Low words:   {score.low_confidence_ratio:.0%}")
        print("--- text ---")
        print(text)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
