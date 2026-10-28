from engine.evaluate import evaluate, normalize_amount


def test_cross_seller_duplicate_is_stop() -> None:
    result = evaluate(
        {"amount": "1800.00", "recipient": "Thabo Sneakers", "reference": "SNK1800"},
        {"amount": "1800.00", "recipient": "Thabo Sneakers", "reference": "SNK1800"},
        ocr_confidence=0.9,
        dup_result={"found": True, "same_seller": False},
    )
    assert result["verdict"] == "STOP"
    assert result["reasons"] == ["duplicate_image"]


def test_amount_mismatch_is_wait() -> None:
    result = evaluate(
        {"amount": "500.00", "recipient": "Thabo Sneakers", "reference": "SNK1800"},
        {"amount": "1800.00", "recipient": "Thabo Sneakers", "reference": "SNK1800"},
        ocr_confidence=0.9,
        dup_result={"found": False, "same_seller": False},
    )
    assert result["verdict"] == "WAIT"
    assert "amount_mismatch" in result["reasons"]


def test_normalize_south_african_amount() -> None:
    assert normalize_amount("R 1 800.00") == 1800.0
    assert normalize_amount("1,800.00") == 1800.0
