"""Extract payment amount, recipient and reference from OCR text.

The parser is intentionally rule-based and deterministic. It understands the
common South African bank layouts and amount formats:

* ``R1,800.00`` / ``R 1 800.00`` / ``1800.00``
* ``ZAR 1 800`` / ``R1,800`` / ``R 1 800,00``

The result is a plain :class:`ExtractedFields` object whose ``amount`` is a
float, matching ``contracts/verdict.example.json``.

Command line usage::

    python ocr/extract.py --text "Paid R1,800.00 to Thabo Sneakers"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from typing import Any

MAX_AMOUNT = 1_000_000_000.0

# A number with optional thousands separators and cents. Group separators may
# be spaces (common in SA banking apps) or commas.
_NUMBER_PATTERN = (
    r"(?:\d{1,3}(?:[ ,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)"
)

_CURRENCY_AMOUNT_RE = re.compile(
    rf"(?<![\w])(?:ZAR|R)[ \t]*(?P<number>{_NUMBER_PATTERN})(?![\w])",
    re.IGNORECASE,
)

_AMOUNT_KEYWORD_RE = re.compile(
    rf"(?i)\b(?:amount|total|paid|sent|transferred|transfer|debited|credited|"
    rf"value|due)[^\d\n]{{0,25}}(?P<number>{_NUMBER_PATTERN})(?![\w])"
)

_STANDALONE_AMOUNT_RE = re.compile(
    rf"(?<![\w.,])(?P<number>{_NUMBER_PATTERN})(?![\w.,])"
)

_AMOUNT_CONTEXT_PENALTY = re.compile(
    r"(?:ref|reference|transaction[ \t]+id|payment[ \t]+id|phone|cell|tel|"
    r"mobile|account|acc|card|date|time)[^a-z0-9]{0,10}$",
    re.IGNORECASE,
)
_AMOUNT_CONTEXT_BONUS = re.compile(
    r"(?:amount|grand[ \t]+total|total|paid|payment|sent|transferred|"
    r"transfer|debited|credited|value|due)[^a-z0-9]{0,10}$",
    re.IGNORECASE,
)
_AMOUNT_CONTEXT_FEE = re.compile(
    r"(?:fee|fees|charge|charges|balance|available|limit)[^a-z0-9]{0,10}$",
    re.IGNORECASE,
)

_RECIPIENT_LABELS = (
    r"paid[ \t]+to|payment[ \t]+to|pay[ \t]+to|sent[ \t]+to|send[ \t]+to|"
    r"transferred[ \t]+to|transfer[ \t]+to|"
    r"beneficiary(?:[ \t]+name)?|recipient(?:[ \t]+name)?|payee(?:[ \t]+name)?|to"
)
_RECIPIENT_LINE_RE = re.compile(
    rf"^(?P<label>{_RECIPIENT_LABELS})\b[ \t]*(?:[:#\-–—][ \t]*)?(?P<value>.*)$",
    re.IGNORECASE,
)
_INLINE_RECIPIENT_RE = re.compile(
    r"(?i)\b(?:paid|sent|transferred|payment|transfer)\b[^\n]{0,80}?"
    r"\bto[ \t]+(?P<value>[^\n]+)"
)

_RECIPIENT_STOP_WORDS = (
    r"reference|ref|amount|total|date|time|from|bank|account|acc(?:ount)?|"
    r"phone|mobile|cell|invoice|payment[ \t]+id|transaction[ \t]+id|status"
)
_RECIPIENT_STOP_RE = re.compile(
    rf"(?i)\s+(?:{_RECIPIENT_STOP_WORDS})\b"
)
_RECIPIENT_BAD_VALUES = {
    "successful",
    "success",
    "completed",
    "complete",
    "pending",
    "processing",
    "paid",
    "sent",
    "payment",
    "transfer",
    "bank",
    "account",
    "card",
    "none",
    "n/a",
    "na",
    "to",
    "recipient",
    "beneficiary",
    "payee",
}

_REFERENCE_LABELS = (
    r"payment[ \t]+reference|transaction[ \t]+reference|payment[ \t]+id|"
    r"transaction[ \t]+id|reference|ref|invoice(?:[ \t]+(?:no|number|#))?|"
    r"order(?:[ \t]+(?:no|number|#))?"
)
_REFERENCE_LINE_RE = re.compile(
    rf"^(?P<label>{_REFERENCE_LABELS})\b"
    r"[ \t]*(?P<qualifier>(?:no\.?|number|#))?[ \t]*"
    r"(?:[:#\-–—][ \t]*)?(?P<value>.*)$",
    re.IGNORECASE,
)
_INLINE_REFERENCE_RE = re.compile(
    r"(?i)\b(?:reference|ref|payment[ \t]+id|transaction[ \t]+id)\b"
    r"[ \t]*(?:no\.?|number|is|was|#)?[ \t]*[:#\-–—]?[ \t]*"
    r"(?P<value>[A-Za-z0-9][A-Za-z0-9._/-]{1,39})"
)
_REFERENCE_STOP_WORDS = (
    r"reference|ref|amount|total|date|time|from|to|bank|account|phone|"
    r"mobile|cell|invoice|status"
)
_REFERENCE_STOP_RE = re.compile(
    rf"(?i)\s+(?:{_REFERENCE_STOP_WORDS})\b"
)
_REFERENCE_BAD_VALUES = {
    "reference",
    "ref",
    "none",
    "na",
    "n/a",
    "notavailable",
    "no",
    "number",
}


@dataclass(frozen=True)
class ExtractedFields:
    """Payment fields found in an OCR transcript."""

    amount: float | None
    recipient: str | None
    reference: str | None
    raw_text: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Return the fields in the shape expected by the verdict contract."""
        return {
            "amount": self.amount,
            "recipient": self.recipient,
            "reference": self.reference,
        }

    @property
    def is_complete(self) -> bool:
        return self.amount is not None and self.recipient is not None


def _normalise_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text or ""))
    text = text.translate(
        str.maketrans(
            {
                "\u00a0": " ",
                "\u202f": " ",
                "\u2007": " ",
                "\u2011": "-",
                "\u2013": "-",
                "\u2014": "-",
            }
        )
    )
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def parse_amount(raw: str) -> float | None:
    """Parse ``R1,800.00`` / ``1 800,00`` / ``1.800,00`` / ``1800.00``."""
    value = (raw or "").strip().replace(" ", "")
    if not value:
        return None

    # Drop currency symbols/labels and any other OCR decoration.
    value = re.sub(r"[^\d.,]", "", value)
    if not value:
        return None

    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        parts = value.split(",")
        if len(parts[-1]) in (1, 2):
            value = value[: -(len(parts[-1]) + 1)] + "." + parts[-1]
        else:
            value = value.replace(",", "")
    elif value.count(".") > 1:
        head, _, tail = value.rpartition(".")
        value = head.replace(".", "") + "." + tail

    try:
        amount = float(value)
    except ValueError:
        return None

    if amount <= 0 or amount > MAX_AMOUNT:
        return None
    return round(amount, 2)


def _amount_context_score(text: str, start: int) -> int:
    before = text[max(0, start - 60) : start]
    score = 0
    if _AMOUNT_CONTEXT_BONUS.search(before):
        score += 40
    if _AMOUNT_CONTEXT_FEE.search(before):
        score -= 50
    if _AMOUNT_CONTEXT_PENALTY.search(before):
        score -= 70
    return score


def _standalone_is_plausible(raw: str) -> bool:
    if not ("." in raw or "," in raw or re.search(r"[ ,]\d{3}", raw)):
        # Bare integers such as years, phone numbers and reference IDs are too
        # ambiguous without a currency symbol or keyword.
        return False
    if raw.startswith("0") and (" " in raw or "," in raw):
        # Likely a South African phone number such as "082 123 4567".
        return False
    return True


def _extract_amount(text: str) -> float | None:
    candidates: list[tuple[float, int, float]] = []

    for match in _CURRENCY_AMOUNT_RE.finditer(text):
        raw = match.group("number")
        amount = parse_amount(raw)
        if amount is None:
            continue
        score = 100 + _amount_context_score(text, match.start())
        if score <= 50:
            continue
        candidates.append((score, match.start(), amount))

    for match in _AMOUNT_KEYWORD_RE.finditer(text):
        between = text[match.start() : match.start("number")].lower()
        if "ref" in between or "phone" in between:
            continue
        raw = match.group("number")
        amount = parse_amount(raw)
        if amount is None:
            continue
        score = 80 + _amount_context_score(text, match.start("number"))
        if score <= 50:
            continue
        candidates.append((score, match.start("number"), amount))

    for match in _STANDALONE_AMOUNT_RE.finditer(text):
        raw = match.group("number")
        if not _standalone_is_plausible(raw):
            continue
        amount = parse_amount(raw)
        if amount is None:
            continue
        score = 20 + _amount_context_score(text, match.start())
        if score <= 0:
            continue
        candidates.append((score, match.start(), amount))

    if not candidates:
        return None

    # Highest score wins; on a tie, prefer the amount that appears first.
    _score, _start, amount = max(candidates, key=lambda item: (item[0], -item[1]))
    return amount


def _next_non_empty_line(lines: list[str], index: int) -> str | None:
    for line in lines[index:]:
        if not line:
            continue
        if _RECIPIENT_LINE_RE.match(line) or _REFERENCE_LINE_RE.match(line):
            return None
        return line
    return None


def _clean_recipient(value: str) -> str | None:
    value = re.sub(
        r"(?i)^(?:name|account(?:\s+name)?|acc(?:ount)?\s+no\.?)\s*[:\-]\s*",
        "",
        value,
    )
    value = _RECIPIENT_STOP_RE.split(value, maxsplit=1)[0]
    value = re.split(r"\s*[|•]\s*", value, maxsplit=1)[0]
    value = re.split(r"(?i)\s+(?:on|at)\s+\d{1,2}[ /-]", value, maxsplit=1)[0]
    value = value.strip(" \t:;,.\\-–—#")
    value = re.sub(r"\s+", " ", value)

    if len(value) < 2 or len(value) > 80:
        return None
    if not re.search(r"[A-Za-z]", value):
        return None
    if re.fullmatch(r"(?i)(?:r|zar)\s*[\d\s.,]+", value):
        return None
    if value.casefold() in _RECIPIENT_BAD_VALUES:
        return None
    return value


def _extract_recipient(text: str) -> str | None:
    lines = text.split("\n")
    candidates: list[tuple[int, int, str]] = []

    for index, line in enumerate(lines):
        match = _RECIPIENT_LINE_RE.match(line)
        if not match:
            continue

        label = re.sub(r"\s+", " ", match.group("label").lower())
        value = _clean_recipient(match.group("value"))
        if not value:
            following = _next_non_empty_line(lines, index + 1)
            value = _clean_recipient(following) if following else None
        if not value:
            continue

        if label.startswith("beneficiary") or label.startswith("recipient") or label.startswith("payee"):
            score = 100
        elif label in {"paid to", "payment to", "pay to", "sent to", "send to", "transferred to", "transfer to"}:
            score = 90
        else:
            score = 60
        candidates.append((score, index, value))

    for match in _INLINE_RECIPIENT_RE.finditer(text):
        value = _clean_recipient(match.group("value"))
        if value:
            candidates.append((80, text[: match.start()].count("\n"), value))

    if not candidates:
        return None

    def dedupe_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.casefold())

    best_by_value: dict[str, tuple[int, int, str]] = {}
    for candidate in candidates:
        key = dedupe_key(candidate[2])
        if not key:
            continue
        current = best_by_value.get(key)
        if current is None or (candidate[0], -candidate[1]) > (current[0], -current[1]):
            best_by_value[key] = candidate

    _score, _line, recipient = max(
        best_by_value.values(), key=lambda item: (item[0], -item[1])
    )
    return recipient


def _clean_reference(value: str) -> str | None:
    value = _REFERENCE_STOP_RE.split(value, maxsplit=1)[0]
    value = re.split(r"\s*[|•]\s*", value, maxsplit=1)[0]
    value = value.strip(" \t:;,.\\-–—#")
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"[^A-Za-z0-9._/-]", "", value)

    if len(value) < 2 or len(value) > 40:
        return None
    if value.casefold() in _REFERENCE_BAD_VALUES:
        return None
    if not re.search(r"\d", value) and not value.isupper():
        return None
    return value


def _extract_reference(text: str) -> str | None:
    lines = text.split("\n")
    candidates: list[tuple[int, int, str]] = []

    for index, line in enumerate(lines):
        match = _REFERENCE_LINE_RE.match(line)
        if not match:
            continue

        label = re.sub(r"\s+", " ", match.group("label").lower())
        value = _clean_reference(match.group("value"))
        if not value:
            following = _next_non_empty_line(lines, index + 1)
            value = _clean_reference(following) if following else None
        if not value:
            continue

        if label.startswith("payment reference") or label.startswith("transaction reference"):
            score = 100
        elif label == "reference":
            score = 95
        else:
            score = 85
        candidates.append((score, index, value))

    for match in _INLINE_REFERENCE_RE.finditer(text):
        value = _clean_reference(match.group("value"))
        if value:
            candidates.append((80, text[: match.start()].count("\n"), value))

    if not candidates:
        return None

    _score, _line, reference = max(candidates, key=lambda item: (item[0], -item[1]))
    return reference


def extract_fields(text: str) -> ExtractedFields:
    """Extract amount, recipient and reference from OCR text."""
    normalised = _normalise_text(text)
    if not normalised:
        return ExtractedFields(amount=None, recipient=None, reference=None)

    return ExtractedFields(
        amount=_extract_amount(normalised),
        recipient=_extract_recipient(normalised),
        reference=_extract_reference(normalised),
        raw_text=text or "",
    )


def extract_amount(text: str) -> float | None:
    return _extract_amount(_normalise_text(text))


def extract_recipient(text: str) -> str | None:
    return _extract_recipient(_normalise_text(text))


def extract_reference(text: str) -> str | None:
    return _extract_reference(_normalise_text(text))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract payment fields from an OCR transcript"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="raw OCR text")
    parser.add_argument("--json", action="store_true", help="print JSON")
    args = parser.parse_args(argv)

    try:
        fields = extract_fields(args.text or "")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(fields.as_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"Amount:    {fields.amount}")
        print(f"Recipient: {fields.recipient}")
        print(f"Reference: {fields.reference}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
