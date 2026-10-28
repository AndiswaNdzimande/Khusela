"""OCR pipeline wrapper with Digital Forensics."""
from ocr.extract import extract_fields
from ocr.forensics import analyze_document_forensics
from ocr.phash import phash
from ocr.tesseract_engine import run_ocr


def analyse_image(image_bytes: bytes) -> dict:
    """Analyse a payment screenshot and extract structured fields, perceptual hash, and forensic indicators."""
    ocr = run_ocr(image_bytes)
    fields = extract_fields(ocr.text)
    forensics = analyze_document_forensics(image_bytes, ocr_text=ocr.text)
    return {
        "amount": fields.amount,
        "recipient": fields.recipient,
        "reference": fields.reference,
        "ocr_confidence": float(ocr.confidence),
        "raw_text": ocr.text,
        "phash": phash(image_bytes),
        "timestamp": getattr(fields, "timestamp", None),
        "forensics": forensics,
    }
