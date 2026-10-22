# backend/engine/evaluate.py

def evaluate(extracted: dict, expected: dict, ocr_confidence: float, dup_result: dict) -> dict:
    """
    TASK-09: Stub for the rule engine.
    Returns a hardcoded verdict so the API and Frontend teams can build.
    """
    return {
        "verdict": "WAIT",
        "reasons": ["stub_mode_active"],
        "explanation": "This is a stub explanation. Please verify funds in your bank app.",
        "confidence": 0.99,
        "is_duplicate": False
    }