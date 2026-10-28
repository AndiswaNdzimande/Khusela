"""Unit tests for Document Forensics & Tampering Engine (ELA, MRZ, Metadata, PDF Stream)."""
import io
import pytest
from PIL import Image

from ocr.forensics import (
    calculate_mrz_check_digit,
    validate_mrz_checksum,
    parse_and_validate_mrz,
    compute_ela,
    analyze_metadata,
    analyze_pdf_stream,
    analyze_document_forensics,
)


def test_mrz_icao_9303_example_calculation():
    """Verify exact ICAO Doc 9303 checksum arithmetic for Document Number L898902C3."""
    # L(11)*7 + 8*3 + 9*1 + 8*7 + 9*3 + 0*1 + 2*7 + C(12)*3 + 3*1 = 246 => 246 % 10 = 6
    assert calculate_mrz_check_digit("L898902C3") == "6"
    assert validate_mrz_checksum("L898902C3", "6") is True
    assert validate_mrz_checksum("L898902C3", "7") is False


def test_mrz_td3_passport_validation():
    """Verify parsing and validation of standard TD3 Passport MRZ."""
    mrz_text = (
        "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\n"
        "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
    )
    res = parse_and_validate_mrz(mrz_text)
    assert res is not None
    assert res["is_valid"] is True
    assert res["tampered"] is False
    assert res["document_number"] == "L898902C3"
    assert res["checks"]["document_number"] is True
    assert res["checks"]["dob"] is True
    assert res["checks"]["expiry"] is True


def test_mrz_td3_tampered_flagged():
    """Tampering with a single character in the document number breaks the checksum."""
    mrz_tampered = (
        "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\n"
        "L898902C46UTO7408122F1204159ZE184226B<<<<<10"
    )
    res = parse_and_validate_mrz(mrz_tampered)
    assert res is not None
    assert res["is_valid"] is False
    assert res["tampered"] is True
    assert res["checks"]["document_number"] is False
    assert "Document number checksum failed" in res["errors"][0]


def test_compute_ela_runs_and_returns_metrics():
    """Ensure Error Level Analysis returns structural metrics."""
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), color="blue").save(buf, format="JPEG")
    res = compute_ela(buf.getvalue())
    assert "ela_mean" in res
    assert "anomaly_ratio" in res
    assert "tampered" in res
    assert res["tampered"] is False


def test_metadata_detects_suspicious_editor():
    """Metadata inspection detects consumer editor provenance (Photoshop / Canva)."""
    fake_ps_file = b"%PDF-1.4\nProducer: Adobe Photoshop 2024\nxmpMM:History: saved by Photoshop\n"
    res = analyze_metadata(fake_ps_file)
    assert res["tampered"] is True
    assert any("Adobe Photoshop" in s for s in res["software"])
    assert res["edit_history_found"] is True


def test_pdf_stream_detects_white_box_masking():
    """PDF stream analysis flags white-box vector rectangles masking original content."""
    # Simulates: 1 1 1 rg (white fill) 120 500 80 15 re f (filled rectangle)
    tampered_pdf = (
        b"%PDF-1.4\n"
        b"1 1 1 rg\n"
        b"120 500 80 15 re f\n"
        b"0 0 0 rg\n"
        b"120 500 Td ($8,500) Tj\n"
    )
    res = analyze_pdf_stream(tampered_pdf)
    assert res["tampered"] is True
    assert res["white_boxes_found"] >= 1


def test_unified_forensic_pipeline():
    """End-to-end forensic analyzer rules apply to PDFs only."""
    # Non-PDF image: forensics skipped
    buf = io.BytesIO()
    Image.new("RGB", (120, 120), color="white").save(buf, format="JPEG")
    img_res = analyze_document_forensics(buf.getvalue(), ocr_text="Invoice #1234", is_pdf=False)
    assert img_res["is_pdf"] is False
    assert img_res["tampering_detected"] is False

    # Clean PDF: is_pdf=True, no tampering
    clean_pdf = b"%PDF-1.4\n1 0 obj\n<< /Producer (Apache FOP) >>\nendobj\n"
    pdf_res = analyze_document_forensics(clean_pdf, ocr_text="Invoice #1234", is_pdf=True)
    assert pdf_res["is_pdf"] is True
    assert pdf_res["tampering_detected"] is False
    assert pdf_res["severity"] == "CLEAN"

    # Tampered PDF with Photoshop metadata: flagged
    dirty_pdf = b"%PDF-1.4\nProducer: Adobe Photoshop CC\nxmpMM:History: saved\n"
    dirty_res = analyze_document_forensics(dirty_pdf, is_pdf=True)
    assert dirty_res["is_pdf"] is True
    assert dirty_res["tampering_detected"] is True
    assert "suspicious_editor_metadata" in dirty_res["reasons"]
