"""Pydantic schemas for the /check endpoint (matches contracts/verdict.schema.json)."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class CheckResponse(BaseModel):
    check_id: str
    verdict: str                        # MATCH | WAIT | STOP
    reasons: List[str]
    explanation: str
    confidence: Optional[float] = None
    is_duplicate: bool
    extracted: Dict[str, Any] = {}
    expected: Dict[str, Any] = {}
    duplicate: Dict[str, Any] = {}
    raw_ocr_text: Optional[str] = None
    explanation_source: str = "template"
    bank_reminder: str = (
        "Always confirm with your bank before releasing goods. "
        "Khusela checks the slip only — it cannot guarantee that funds have cleared."
    )


class HealthResponse(BaseModel):
    status: str
