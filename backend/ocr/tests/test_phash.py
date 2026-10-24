import io
import json

import pytest
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from ocr.phash import (
    DEFAULT_HAMMING_THRESHOLD,
    DEFAULT_HASH_SIZE,
    DuplicateMatch,
    evaluate_threshold,
    find_near_duplicates,
    hamming_distance,
    is_near_duplicate,
    main,
    phash,
    phash_int,
    closest_match,
    tune_threshold,
)


def _font(size: int = 38):
    for name in (
        "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "arial.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _screenshot(
    *,
    amount: str = "R1,800.00",
    recipient: str = "Thabo Sneakers",
    reference: str = "SNK1800",
    heading: str = "PAYMENT SENT",
    size: tuple[int, int] = (900, 480),
    background: tuple[int, int, int] = (255, 255, 255),
    foreground: tuple[int, int, int] = (20, 20, 20),
) -> Image.Image:
    image = Image.new("RGB", size, background)
    draw = ImageDraw.Draw(image)
    normal = _font(38)
    amount_font = _font(64)
    draw.text((45, 25), heading, fill=foreground, font=normal)
    draw.text((45, 85), f"Amount: {amount}", fill=foreground, font=amount_font)
    draw.text((45, 190), f"To: {recipient}", fill=foreground, font=normal)
    draw.text((45, 268), f"Reference: {reference}", fill=foreground, font=normal)
    return image


def _jpeg(image: Image.Image, quality: int = 30) -> Image.Image:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    with Image.open(buffer) as opened:
        opened.load()
        return opened.copy()


def _flip_bits(hex_hash: str, count: int) -> str:
    value = int(hex_hash, 16)
    for bit in range(count):
        value ^= 1 << bit
    return f"{value:0{len(hex_hash)}x}"


def test_default_hash_is_high_resolution_and_stable():
    image = _screenshot()

    assert DEFAULT_HASH_SIZE == 32
    assert DEFAULT_HAMMING_THRESHOLD == 28
    assert phash(image) == phash(image)
    assert len(phash(image)) == 256
    assert len(phash(image, hash_size=8)) == 16


def test_phash_int_round_trips_to_hex():
    image = _screenshot()

    integer = phash_int(image)
    assert int(phash(image), 16) == integer
    assert integer.bit_length() <= DEFAULT_HASH_SIZE * DEFAULT_HASH_SIZE


def test_phash_accepts_paths_bytes_file_objects_and_pil_images(tmp_path):
    source = tmp_path / "screenshot.png"
    _screenshot().save(source)
    payload = source.read_bytes()

    expected = phash(_screenshot())
    assert phash(source) == expected
    assert phash(payload) == expected
    assert phash(io.BytesIO(payload)) == expected
    with Image.open(source) as opened:
        assert phash(opened) == expected


def test_resized_screenshot_is_a_near_duplicate():
    screenshot = _screenshot()
    resized = screenshot.resize((450, 240), Image.Resampling.LANCZOS)

    distance = hamming_distance(phash(screenshot), phash(resized))

    assert distance <= DEFAULT_HAMMING_THRESHOLD
    assert is_near_duplicate(phash(screenshot), phash(resized))


def test_jpeg_and_photoshop_like_changes_are_near_duplicates():
    screenshot = _screenshot()
    variants = [
        _jpeg(screenshot, quality=30),
        ImageEnhance.Brightness(screenshot).enhance(1.12),
        ImageEnhance.Brightness(screenshot).enhance(0.85),
        ImageEnhance.Contrast(screenshot).enhance(0.9),
        screenshot.filter(ImageFilter.GaussianBlur(0.6)),
        _jpeg(
            ImageEnhance.Brightness(
                screenshot.resize((600, 320), Image.Resampling.LANCZOS)
            ).enhance(1.08),
            quality=40,
        ),
    ]

    original_hash = phash(screenshot)
    for variant in variants:
        distance = hamming_distance(original_hash, phash(variant))
        assert distance <= DEFAULT_HAMMING_THRESHOLD


@pytest.mark.parametrize(
    "changed",
    [
        {"amount": "R1,900.00"},
        {"amount": "R2,450.50"},
        {"recipient": "Ndlovu & Sons"},
        {"reference": "ABC9999"},
    ],
    ids=["close-amount", "different-amount", "recipient", "reference"],
)
def test_changed_payment_details_are_not_duplicates(changed):
    original = _screenshot()
    changed_image = _screenshot(**changed)

    distance = hamming_distance(phash(original), phash(changed_image))

    assert distance > DEFAULT_HAMMING_THRESHOLD
    assert not is_near_duplicate(phash(original), phash(changed_image))


def test_different_bank_layout_and_dark_mode_are_not_duplicates():
    original = _screenshot()
    capitec = _screenshot(
        heading="CAPITEC",
        amount="R 1 800.00",
        recipient="Ndlovu & Sons",
        reference="INV2026",
        background=(240, 245, 255),
    )
    dark_mode = _screenshot(
        background=(22, 22, 22),
        foreground=(245, 245, 245),
    )

    original_hash = phash(original)
    assert not is_near_duplicate(original_hash, phash(capitec))
    assert not is_near_duplicate(original_hash, phash(dark_mode))


def test_near_duplicate_corpus_has_clear_separation():
    screenshot = _screenshot()
    original_hash = phash(screenshot)

    near = {
        "resize": screenshot.resize((540, 288), Image.Resampling.LANCZOS),
        "jpeg": _jpeg(screenshot, quality=20),
        "brightness": ImageEnhance.Brightness(screenshot).enhance(1.15),
        "darkened": ImageEnhance.Brightness(screenshot).enhance(0.85),
        "contrast": ImageEnhance.Contrast(screenshot).enhance(0.85),
        "blur": screenshot.filter(ImageFilter.GaussianBlur(0.8)),
        "combined": _jpeg(
            ImageEnhance.Brightness(
                screenshot.resize((600, 320), Image.Resampling.LANCZOS)
            ).enhance(1.08),
            quality=25,
        ),
    }
    different = {
        "amount": _screenshot(amount="R2,450.50"),
        "close-amount": _screenshot(amount="R1,900.00"),
        "recipient": _screenshot(recipient="Ndlovu & Sons"),
        "reference": _screenshot(reference="ABC9999"),
        "layout": _screenshot(
            heading="CAPITEC",
            background=(240, 245, 255),
            reference="INV2026",
        ),
    }

    near_distances = {
        name: hamming_distance(original_hash, phash(image))
        for name, image in near.items()
    }
    different_distances = {
        name: hamming_distance(original_hash, phash(image))
        for name, image in different.items()
    }

    assert max(near_distances.values()) < min(different_distances.values())
    assert max(near_distances.values()) <= DEFAULT_HAMMING_THRESHOLD
    assert min(different_distances.values()) > DEFAULT_HAMMING_THRESHOLD


def test_threshold_is_inferred_from_hash_length():
    hash_64 = "f" * 16
    hash_1024 = "f" * 256

    assert is_near_duplicate(hash_64, _flip_bits(hash_64, 5))
    assert not is_near_duplicate(hash_64, _flip_bits(hash_64, 6))
    assert is_near_duplicate(hash_1024, _flip_bits(hash_1024, 28))
    assert not is_near_duplicate(hash_1024, _flip_bits(hash_1024, 29))


def test_hamming_distance_counts_differing_bits():
    assert hamming_distance("0000", "0000") == 0
    assert hamming_distance("0000", "000f") == 4
    assert hamming_distance("ffff", "0000") == 16
    assert hamming_distance(0b1010, 0b0011) == 2
    assert hamming_distance("000f", 15) == 0


def test_invalid_hashes_and_thresholds_are_rejected():
    with pytest.raises(ValueError):
        hamming_distance("00", "0000")
    with pytest.raises(ValueError):
        hamming_distance("not-a-hash", "00")
    with pytest.raises(TypeError):
        hamming_distance(1.5, 0)
    with pytest.raises(ValueError):
        hamming_distance(-1, 0)
    with pytest.raises(ValueError):
        is_near_duplicate("00", "00", threshold=-1)
    with pytest.raises(ValueError):
        phash(_screenshot(), hash_size=0)
    with pytest.raises(ValueError):
        phash(_screenshot(), highfreq_factor=0)


def test_find_near_duplicates_sorts_and_filters_candidates():
    target = "f" * 256
    candidates = {
        "exact": target,
        "one": _flip_bits(target, 1),
        "twenty-eight": _flip_bits(target, 28),
        "twenty-nine": _flip_bits(target, 29),
        "far": _flip_bits(target, 80),
    }

    matches = find_near_duplicates(target, candidates, threshold=28)

    assert [match.key for match in matches] == ["exact", "one", "twenty-eight"]
    assert [match.distance for match in matches] == [0, 1, 28]
    assert find_near_duplicates(target, candidates, threshold=28, limit=1) == [
        DuplicateMatch("exact", 0, 28)
    ]
    assert find_near_duplicates(target, [], threshold=28) == []
    assert find_near_duplicates(target, target, threshold=28)[0].key == target


def test_closest_match_returns_the_nearest_candidate_even_if_it_is_not_a_duplicate():
    target = "f" * 256
    candidates = {
        "near": _flip_bits(target, 2),
        "nearest": _flip_bits(target, 1),
    }

    match = closest_match(target, candidates, threshold=0)

    assert match == DuplicateMatch("nearest", 1, 0)
    assert match is not None
    assert match.is_duplicate is False
    assert match.as_dict() == {
        "key": "nearest",
        "distance": 1,
        "threshold": 0,
        "is_duplicate": False,
    }
    assert closest_match(target, []) is None


def test_evaluate_threshold_returns_classification_metrics():
    base = "f" * 256
    pairs = [
        (base, _flip_bits(base, 2), True),
        (base, _flip_bits(base, 10), True),
        (base, _flip_bits(base, 5), False),
        (base, _flip_bits(base, 30), False),
    ]

    report = evaluate_threshold(pairs, threshold=10)

    assert report.true_positives == 2
    assert report.false_positives == 1
    assert report.true_negatives == 1
    assert report.false_negatives == 0
    assert report.precision == pytest.approx(2 / 3, abs=1e-4)
    assert report.recall == 1.0
    assert report.f1 == pytest.approx(0.8, abs=1e-4)
    assert report.accuracy == 0.75
    assert report.total == 4
    assert report.as_dict()["threshold"] == 10


def test_tune_threshold_picks_a_threshold_between_the_classes():
    base = "f" * 256
    pairs = [
        (base, base, True),
        (base, _flip_bits(base, 5), True),
        (base, _flip_bits(base, 20), True),
        (base, _flip_bits(base, 32), False),
        (base, _flip_bits(base, 50), False),
    ]

    report = tune_threshold(pairs)

    assert report.true_positives == 3
    assert report.false_positives == 0
    assert report.false_negatives == 0
    assert 20 <= report.threshold < 32
    assert report.precision == 1.0
    assert report.recall == 1.0


def test_tune_threshold_rejects_empty_pairs():
    with pytest.raises(ValueError):
        tune_threshold([])


def test_cli_tunes_threshold_from_labelled_pairs(tmp_path, capsys):
    original = tmp_path / "original.png"
    resent = tmp_path / "resent.png"
    different = tmp_path / "different.png"
    _screenshot().save(original)
    _screenshot().resize((450, 240), Image.Resampling.LANCZOS).save(resent)
    _screenshot(amount="R2,450.50").save(different)
    labels = tmp_path / "labels.json"
    labels.write_text(
        json.dumps(
            [
                {"a": "original.png", "b": "resent.png", "duplicate": True},
                {"a": "original.png", "b": "different.png", "duplicate": False},
            ]
        ),
        encoding="utf-8",
    )

    code = main(["--tune", str(labels), "--json"])

    assert code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["false_positives"] == 0
    assert output["false_negatives"] == 0
    assert output["threshold"] > 0


def test_cli_compares_a_near_duplicate(tmp_path, capsys):
    original = tmp_path / "original.png"
    resized = tmp_path / "resized.png"
    _screenshot().save(original)
    _screenshot().resize((450, 240), Image.Resampling.LANCZOS).save(resized)

    code = main(
        [
            "--image",
            str(original),
            "--compare",
            str(resized),
            "--json",
        ]
    )

    assert code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["image"] == str(original)
    assert output["hash_size"] == DEFAULT_HASH_SIZE
    assert output["matches"][0]["is_duplicate"] is True
    assert output["matches"][0]["distance"] <= DEFAULT_HAMMING_THRESHOLD
