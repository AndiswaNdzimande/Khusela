import pytest

from ocr.confidence import (
    ConfidenceScore,
    compute_confidence,
    confidence_label,
    parse_tsv,
)

HEADER = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
    "left\ttop\twidth\theight\tconf\ttext"
)


def _tsv(rows, *, line: int = 1) -> str:
    lines = [HEADER]
    for index, (word, confidence) in enumerate(rows, start=1):
        lines.append(
            f"5\t1\t1\t1\t{line}\t{index}\t0\t0\t10\t10\t{confidence}\t{word}"
        )
    return "\n".join(lines)


def test_parse_tsv_reconstructs_lines_and_scores_words():
    tsv = _tsv(
        [("PAYMENT", 96.0), ("SENT", 94.0), ("Amount:", 92.0)],
    )

    text, score = parse_tsv(tsv)

    assert text == "PAYMENT SENT Amount:"
    assert score.word_count == 3
    assert score.low_confidence_ratio == 0.0
    assert score.score == pytest.approx(0.94)
    assert score.label == "high"
    assert score.is_reliable is True


def test_low_confidence_words_reduce_the_score():
    tsv = _tsv(
        [
            ("PAYMENT", 96.0),
            ("SENT", 95.0),
            ("Assourt.", 45.0),
            ("R1,800.00", 62.0),
            ("Ta", 60.0),
            ("Thabo", 48.0),
        ]
    )

    score = compute_confidence(tsv)

    assert score.low_confidence_ratio == pytest.approx(2 / 6, abs=1e-4)
    assert score.score < score.mean_word_confidence
    assert score.score < 0.5
    assert score.label == "low"
    assert score.is_reliable is False


def test_all_low_confidence_words_give_zero_score():
    score = compute_confidence(_tsv([("blur", 20.0), ("blur", 30.0), ("blur", 40.0)]))

    assert score.low_confidence_ratio == 1.0
    assert score.score == 0.0
    assert score.label == "low"


def test_empty_tsv_is_unreliable():
    text, score = parse_tsv("")

    assert text == ""
    assert score == ConfidenceScore(
        score=0.0,
        mean_word_confidence=0.0,
        low_confidence_ratio=0.0,
        word_count=0,
    )


def test_rows_without_real_confidence_still_contribute_text():
    tsv = _tsv([("Thabo", -1.0), ("Sneakers", -1.0)])

    text, score = parse_tsv(tsv)

    assert text == "Thabo Sneakers"
    assert score.word_count == 0
    assert score.score == 0.0


def test_confidence_label_boundaries():
    assert confidence_label(0.0) == "low"
    assert confidence_label(0.49) == "low"
    assert confidence_label(0.5) == "medium"
    assert confidence_label(0.74) == "medium"
    assert confidence_label(0.75) == "high"
    assert confidence_label(1.0) == "high"


def test_score_as_dict_contains_details():
    score = ConfidenceScore(
        score=0.91,
        mean_word_confidence=0.93,
        low_confidence_ratio=0.0,
        word_count=9,
    )

    assert score.as_dict() == {
        "score": 0.91,
        "mean_word_confidence": 0.93,
        "low_confidence_ratio": 0.0,
        "word_count": 9,
        "label": "high",
        "is_reliable": True,
    }
