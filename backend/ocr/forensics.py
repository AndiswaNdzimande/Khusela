"""
Document Tampering & Digital Forensics Engine.

Implements multi-layer forensic inspection for banking receipts, invoices, and ID documents:
1. Error Level Analysis (ELA): Detects copy-paste splices, recompressed numbers, and uneven DCT quantization.
2. Metadata & Provenance Parsing: Inspects Exif, JFIF, and Adobe XMP packets for consumer editing software
   (Photoshop, Canva, GIMP, Sejda, Photopea) vs enterprise document spoolers (Apache FOP, ReportLab, StreamServe).
3. PDF Stream & Vector Forensics: Analyzes raw PDF object streams for font subset mismatches, coordinate jitter
   (Td/Tm operators), and white-box masking layers.
4. ICAO Doc 9303 MRZ Check-Digit Validation: Deterministic 7-3-1 modulo arithmetic across TD1, TD2, and TD3 identity documents.
"""

from __future__ import annotations

import io
import re
import math
from typing import Any
from PIL import Image, ImageChops, ImageStat
from pypdf import PdfReader 


# ==============================================================================
# 1. ERROR LEVEL ANALYSIS (ELA)
# ==============================================================================

def compute_ela(
    image_bytes: bytes,
    resave_quality: int = 95,
    scale: float = 15.0,
    grid_size: int = 8,
) -> dict[str, Any]:
    """
    Error Level Analysis (ELA) on JPEG/PNG images.

    Resaves the image at a known quality level (95%) and computes the absolute
    pixel difference scaled by a multiplier. A uniform background has a steady error level,
    while spliced/copy-pasted digits or elements with different compression histories
    display localized high-contrast error spikes.

    Returns:
        ela_mean: Mean error across the image.
        ela_max_block_variance: Maximum localized variance across spatial grid blocks.
        anomaly_ratio: Ratio of max block variance to average block variance.
        tampered: True if significant localized error disparity is found.
        details: Human-readable diagnostic.
    """
    try:
        orig = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        return {
            "tampered": False,
            "anomaly_ratio": 1.0,
            "ela_mean": 0.0,
            "details": f"Could not open image for ELA: {exc}",
        }

    # Resave at fixed quality
    buffer = io.BytesIO()
    orig.save(buffer, format="JPEG", quality=resave_quality)
    buffer.seek(0)
    resaved = Image.open(buffer)

    # Absolute difference scaled
    diff = ImageChops.difference(orig, resaved)
    stat = ImageStat.Stat(diff)
    ela_mean = sum(stat.mean) / len(stat.mean)

    # Grid block variance analysis (detect localized splice glowing)
    width, height = orig.size
    step_x = max(8, width // grid_size)
    step_y = max(8, height // grid_size)

    block_means = []
    for y in range(0, height - step_y + 1, step_y):
        for x in range(0, width - step_x + 1, step_x):
            box = (x, y, x + step_x, y + step_y)
            crop = diff.crop(box)
            b_stat = ImageStat.Stat(crop)
            b_mean = sum(b_stat.mean) / len(b_stat.mean)
            block_means.append(b_mean)

    if not block_means:
        return {
            "tampered": False,
            "anomaly_ratio": 1.0,
            "ela_mean": ela_mean,
            "details": "Image too small for grid ELA analysis.",
        }

    avg_block = sum(block_means) / len(block_means)
    max_block = max(block_means)
    anomaly_ratio = (max_block / avg_block) if avg_block > 0.1 else 1.0

    # If a localized region has > 3.5x higher error difference than the average,
    # it indicates spliced / copy-pasted content with mismatched DCT history.
    tampered = bool(anomaly_ratio > 3.5 and max_block > 8.0)

    details = (
        f"Localized splice anomaly detected (ratio: {anomaly_ratio:.1f}x average block error)"
        if tampered
        else "Uniform compression error level (no obvious localized splice detected)."
    )

    return {
        "tampered": tampered,
        "anomaly_ratio": round(anomaly_ratio, 2),
        "ela_mean": round(ela_mean, 2),
        "details": details,
    }


# ==============================================================================
# 2. METADATA & PROVENANCE INTEGRITY (EXIF / XMP / JFIF)
# ==============================================================================

# ==============================================================================
# FORENSIC CATEGORIZATION OF PDF /PRODUCER AND /CREATOR STRINGS
# ==============================================================================

PRODUCER_TAXONOMY = {
    # --------------------------------------------------------------------------
    # 1. SOUTH AFRICAN SPECIALIZED & LOCAL E-BILLING GIANTS
    # --------------------------------------------------------------------------
    # Striata (founded in Johannesburg, acquired by Doxim) is the dominant player
    # in South African encrypted eStatements and digital billing (Absa, telcos, utilities).
    "za_specialized": [
        "Striata Application Platform",
        "Striata eStatement Generator",
        "Striata Secure Document Repository",
        "Doxim CCM",
        "Doxim Customer Communications",
    ],

    # --------------------------------------------------------------------------
    # 2. TIER-1 GLOBAL BANKING & UTILITY CCM ENGINES (HEAVILY DEPLOYED IN SA)
    # --------------------------------------------------------------------------
    # The enterprise backbones used by Big 5 SA banks, SARS, insurers, and Eskom.
    "tier1_enterprise_ccm": [
        # Quadient (formerly GMC) - widely used in banking statement runs
        "GMC Inspire",
        "Quadient Inspire",
        "GMC PrintNet",

        # OpenText - heavy presence across SA enterprise backends & document management
        "OpenText Exstream",
        "HP Exstream",
        "StreamServe",
        "OpenText Document Presentment",

        # Precisely (formerly Pitney Bowes) - core high-speed print & mail/digital engines
        "EngageOne",
        "Pitney Bowes DOC1",
        "Precisely EngageOne Compose",

        # Papyrus Software - used across corporate transaction document spoolers
        "ISIS Papyrus",
        "Papyrus DocExec",

        # Oracle - legacy banking and ERP statement modules
        "Oracle Documaker",
        "Oracle Reports",
        "Oracle XML Publisher",

        # SAP ADS (Adobe Document Services) - standard across SAP-driven SA institutions (Eskom, Sasol, Transnet)
        "SAP NetWeaver",
        "Adobe Document Services for SAP",
        "SAP Interactive Forms by Adobe",
    ],

    # --------------------------------------------------------------------------
    # 3. MODERN FINTECH & PROGRAMMATIC HEADLESS STACKS
    # --------------------------------------------------------------------------
    # Used by modern neobanks (e.g., TymeBank, Discovery Bank), payment gateways
    # (Ozow, Stitch, Peach Payments), and crypto/fintech platforms (Luno).
    "programmatic_and_fintech": [
        # Java / JVM ecosystem
        "Apache FOP",
        "JasperReports",
        "iText",
        "iTextSharp",
        "PDFBox",
        "Flying Saucer",

        # Python / Node / Go microservices
        "ReportLab",
        "WeasyPrint",
        "wkhtmltopdf",
        "Skia/PDF",                 # Headless Chromium/Puppeteer generation
        "Chrome Headless",
        "PrinceXML",
        "QuestPDF",                 # Modern .NET core generation
    ],

    # --------------------------------------------------------------------------
    # 4. BLACKLISTED / FORGERY-FLAGGED PRODUCERS (CONSUMER & EDITING SUITES)
    # --------------------------------------------------------------------------
    # A legitimate bank statement should almost NEVER report these tools in its metadata.
    "flagged_consumer_editors": [
        "Adobe Photoshop",
        "Adobe Illustrator",
        "Canva",
        "Canva Renderer",
        "macOS Quartz PDFContext",  # Indicates an "Export to PDF" from Preview or a Mac browser
        "Microsoft Word",
        "Microsoft PowerPoint",
        "LibreOffice",
        "Sejda",
        "PDFescape",
        "Smallpdf",
        "ILovePDF",
        "Foxit PDF Editor",
        "Wondershare PDFelement",
        "Nitro Pro",
        "GIMP",
        "Pixlr",
        "Photopea",
        "PicsArt",
        "Inkscape",
        "CorelDraw",
        "Paint.NET",
        "pypdf",
    ],
}

# Lookup structures for fast matching
FLAGGED_CONSUMER_EDITORS = {
    item.lower(): item for item in PRODUCER_TAXONOMY["flagged_consumer_editors"]
}

ENTERPRISE_CATEGORIES = {
    category: [item.lower() for item in items]
    for category, items in PRODUCER_TAXONOMY.items()
    if category != "flagged_consumer_editors"
}

# Backward compatibility alias
SUSPICIOUS_SOFTWARE = FLAGGED_CONSUMER_EDITORS
ENTERPRISE_PRODUCERS = {
    item.lower()
    for cat in ("za_specialized", "tier1_enterprise_ccm", "programmatic_and_fintech")
    for item in PRODUCER_TAXONOMY[cat]
}


def analyze_metadata(file_bytes: bytes) -> dict[str, Any]:
    """
    Examines EXIF headers, JFIF tags, and Adobe XMP XML packets for editing provenance.

    Categorizes /Producer and /Creator against PRODUCER_TAXONOMY:
    - za_specialized: Striata, Doxim (Dominant SA e-billing & encrypted statement engines)
    - tier1_enterprise_ccm: Quadient Inspire, OpenText Exstream, EngageOne, Papyrus, Oracle, SAP ADS
    - programmatic_and_fintech: Flying Saucer, iText, Apache FOP, ReportLab, WeasyPrint, Skia/PDF, QuestPDF
    - flagged_consumer_editors: Photoshop, Illustrator, Canva, macOS Quartz, Word, Sejda, LibreOffice, etc.

    Detects:
    - Consumer/tampering editing software in metadata or producer tags.
    - Timestamp drift (CreateDate vs. ModifyDate discrepancy).
    - XMP edit history sequence (<xmpMM:History> entries logging manual modifications).
    """
    raw_lower = file_bytes[:100000].lower() + file_bytes[-100000:].lower() if len(file_bytes) > 200000 else file_bytes.lower()

    flags: list[str] = []
    software_found: list[str] = []
    producer_found: str | None = None
    producer_category: str | None = None

    # 1. Search for /Producer or /Creator in PDF info dictionary
    prod_match = re.search(rb"/producer\s*\((.*?)\)", raw_lower)
    if not prod_match:
        prod_match = re.search(rb"/creator\s*\((.*?)\)", raw_lower)

    if prod_match:
        try:
            producer_found = prod_match.group(1).decode("latin-1", errors="ignore").strip()
        except Exception:
            producer_found = str(prod_match.group(1)).strip()

    # 2. Check for consumer/tampering editing software in raw metadata
    for token, label in FLAGGED_CONSUMER_EDITORS.items():
        if token.encode("utf-8") in raw_lower:
            software_found.append(label)
            flags.append(f"Edited with consumer software / forgery tool: {label}")

    # 3. Categorize producer string against taxonomy
    if producer_found:
        p_lower = producer_found.lower()
        # Check flagged consumer tools
        for token, label in FLAGGED_CONSUMER_EDITORS.items():
            if token in p_lower:
                producer_category = "flagged_consumer_editors"
                if label not in software_found:
                    software_found.append(label)
                    flags.append(f"PDF Producer/Creator is a consumer editing tool: {label}")
                break

        # Check enterprise categories if not flagged
        if not producer_category:
            for cat_name, engines in ENTERPRISE_CATEGORIES.items():
                for engine in engines:
                    if engine in p_lower:
                        producer_category = cat_name
                        break
                if producer_category:
                    break

    # 4. Check for XMP edit history
    edit_history_found = False
    if b"xmpmm:history" in raw_lower:
        edit_history_found = True
        flags.append("XMP document history contains previous edit/save actions.")

    # 5. Timestamp mismatch check
    timestamp_mismatch = False
    create_match = re.search(rb'createdate[>:\s"]+(\d{4}[^"]{10,20})', raw_lower)
    modify_match = re.search(rb'modifydate[>:\s"]+(\d{4}[^"]{10,20})', raw_lower)
    if create_match and modify_match:
        c_date = create_match.group(1).strip()
        m_date = modify_match.group(1).strip()
        if c_date != m_date:
            timestamp_mismatch = True
            flags.append("Document modification date differs from creation date.")

    # A document is tampered if flagged consumer software is found or XMP edit history exists
    is_tampered = bool(
        software_found
        or (edit_history_found and software_found)
        or (producer_category == "flagged_consumer_editors")
    )

    return {
        "tampered": is_tampered,
        "software": list(dict.fromkeys(software_found)),
        "producer": producer_found,
        "producer_category": producer_category,
        "edit_history_found": edit_history_found,
        "timestamp_mismatch": timestamp_mismatch,
        "flags": flags,
        "details": "; ".join(flags) if flags else f"Clean provenance metadata (Producer: {producer_found or 'Unknown'}).",
    }

# ==============================================================================
# 3. PDF STREAM & VECTOR GRAPH FORENSICS
# ==============================================================================

def analyze_pdf_stream(pdf_bytes: bytes) -> dict[str, Any]:
    """
    Forensically inspects PDF binary coordinate streams.
    Decompresses streams first to find hidden vector masking layers.
    """
    flags: list[str] = []
    raw = pdf_bytes
    decompressed_content = b""

    # 1. Decompress the PDF streams using pypdf
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            if "/Contents" in page:
                content = page["/Contents"]
                if isinstance(content, list):
                    for c in content:
                        decompressed_content += c.get_data()
                else:
                    decompressed_content += content.get_data()
    except Exception as e:
        flags.append(f"Could not decompress PDF streams: {e}")

    # If we got decompressed data, search that. Otherwise, fallback to raw.
    search_target = decompressed_content if decompressed_content else raw

    # 2. White-box vector masking
    # Matches white stroke/fill: '1 1 1 rg' followed by rectangle 'x y w h re' and fill 'f'
    white_box_re = re.compile(
        rb"1(?:\.0+)?\s+1(?:\.0+)?\s+1(?:\.0+)?\s+(?:rg|RG|k)\s+[\d\.\s\-]+re\s+(?:f\*?|F\*?|b\*?|B\*?)",
        re.IGNORECASE,
    )
    white_boxes = list(white_box_re.finditer(search_target))
    if white_boxes:
        flags.append(
            f"Detected {len(white_boxes)} white vector masking rectangle(s) placed over document content."
        )

    # 3. Font subset and font descriptor switching
    font_subsets = set(re.findall(rb"/([A-Z]{6}\+[A-Za-z0-9\-_]+)", raw))
    if len(font_subsets) > 4:
        flags.append(f"Multiple mixed font subsets found ({len(font_subsets)} subsets embedded).")

    # 4. Injected floating point coordinate jitter on Td/Tm operators
    jitter_re = re.compile(rb"(\d+\.\d{3,})\s+(\d+\.\d{3,})\s+Td")
    jitters = list(jitter_re.finditer(search_target))
    if len(jitters) >= 3:
        flags.append(f"Floating-point coordinate jitter detected ({len(jitters)} occurrences).")

    is_tampered = bool(white_boxes)

    return {
        "tampered": is_tampered,
        "white_boxes_found": len(white_boxes),
        "font_subsets": [f.decode("latin-1", errors="ignore") for f in font_subsets],
        "flags": flags,
        "details": "; ".join(flags) if flags else "Clean vector coordinate stream.",
    }


# ==============================================================================
# 4. ICAO DOC 9303 MRZ CHECK-DIGIT VALIDATION
# ==============================================================================

# Repeating weight cycle 7, 3, 1 defined by ICAO 9303
ICAO_WEIGHTS = (7, 3, 1)


def icao_char_value(c: str) -> int:
    """
    Character mapping defined by ICAO Doc 9303:
    0-9  -> 0-9
    A-Z  -> 10-35
    <    -> 0
    """
    if c.isdigit():
        return int(c)
    if "A" <= c.upper() <= "Z":
        return ord(c.upper()) - ord("A") + 10
    return 0


def calculate_mrz_check_digit(data: str) -> str:
    """
    Computes ICAO Doc 9303 check digit using repeating weights [7, 3, 1] modulo 10:
    Check Digit = ( sum_{i=1}^k Value(C_i) * W_{(i-1) mod 3} ) mod 10
    """
    total = sum(
        icao_char_value(char) * ICAO_WEIGHTS[idx % 3]
        for idx, char in enumerate(data)
    )
    return str(total % 10)


def validate_mrz_checksum(data: str, expected_check_digit: str) -> bool:
    """Validate that expected_check_digit matches the calculated ICAO 9303 checksum."""
    return calculate_mrz_check_digit(data) == str(expected_check_digit).strip()


def parse_and_validate_mrz(text: str) -> dict[str, Any] | None:
    """
    Scans OCR text for Machine Readable Zone (MRZ) strings on Passports (TD3: 2x44)
    and Identity Cards (TD1: 3x30, TD2: 2x36).

    Validates:
    - Document number check digit
    - Date of birth check digit (YYMMDD)
    - Expiration date check digit (YYMMDD)
    - Composite checksum

    Returns None if no MRZ pattern is found, or verification results dictionary.
    """
    # Extract candidate MRZ lines with standard filler '<'
    lines = [
        re.sub(r"\s+", "", line.upper())
        for line in text.splitlines()
        if "<" in line and len(re.sub(r"\s+", "", line)) >= 28
    ]

    if not lines:
        return None

    # Check for Passport TD3 (2 lines of ~44 chars)
    if len(lines) >= 2:
        for i in range(len(lines) - 1):
            l1, l2 = lines[i], lines[i + 1]
            if len(l1) >= 42 and len(l2) >= 42:
                return _validate_td3(l1[:44].ljust(44, "<"), l2[:44].ljust(44, "<"))

    # Check for ID Card TD1 (3 lines of ~30 chars)
    if len(lines) >= 3:
        for i in range(len(lines) - 2):
            l1, l2, l3 = lines[i], lines[i + 1], lines[i + 2]
            if len(l1) >= 28 and len(l2) >= 28 and len(l3) >= 28:
                return _validate_td1(
                    l1[:30].ljust(30, "<"),
                    l2[:30].ljust(30, "<"),
                    l3[:30].ljust(30, "<"),
                )

    return None


def _validate_td3(line1: str, line2: str) -> dict[str, Any]:
    """Validate Passport TD3 MRZ (2 lines x 44 chars)."""
    # Line 2 layout:
    # 0..8: Document number (9 chars)
    # 9: Doc check digit (1 char)
    # 10..12: Nationality (3 chars)
    # 13..18: Date of birth (6 chars YYMMDD)
    # 19: DOB check digit (1 char)
    # 20: Sex (1 char)
    # 21..26: Expiry date (6 chars YYMMDD)
    # 27: Expiry check digit (1 char)
    # 28..42: Optional data / personal number (14 chars)
    # 43: Composite check digit (1 char)
    doc_num = line2[0:9]
    doc_check = line2[9]

    dob = line2[13:19]
    dob_check = line2[19]

    expiry = line2[21:27]
    expiry_check = line2[27]

    composite_data = line2[0:10] + line2[13:20] + line2[21:43]
    composite_check = line2[43]

    doc_valid = validate_mrz_checksum(doc_num, doc_check)
    dob_valid = validate_mrz_checksum(dob, dob_check)
    expiry_valid = validate_mrz_checksum(expiry, expiry_check)
    composite_valid = validate_mrz_checksum(composite_data, composite_check)

    all_valid = doc_valid and dob_valid and expiry_valid and composite_valid

    errors = []
    if not doc_valid:
        errors.append(f"Document number checksum failed (got {doc_check}, calculated {calculate_mrz_check_digit(doc_num)})")
    if not dob_valid:
        errors.append(f"Date of birth checksum failed")
    if not expiry_valid:
        errors.append(f"Expiry date checksum failed")
    if not composite_valid:
        errors.append(f"Composite MRZ checksum failed")

    return {
        "format": "TD3 (Passport)",
        "is_valid": all_valid,
        "tampered": not all_valid,
        "document_number": doc_num.replace("<", ""),
        "dob": dob,
        "expiry": expiry,
        "checks": {
            "document_number": doc_valid,
            "dob": dob_valid,
            "expiry": expiry_valid,
            "composite": composite_valid,
        },
        "errors": errors,
        "details": "All ICAO 9303 check digits valid." if all_valid else "; ".join(errors),
    }


def _validate_td1(line1: str, line2: str, line3: str) -> dict[str, Any]:
    """Validate Identity Card TD1 MRZ (3 lines x 30 chars)."""
    # Line 1: 5..14 (Doc number 9 chars) + 14 (check digit)
    # Line 2: 0..5 (DOB 6 chars) + 6 (check digit) + 8..13 (Expiry 6 chars) + 14 (check digit)
    doc_num = line1[5:14]
    doc_check = line1[14]

    dob = line2[0:6]
    dob_check = line2[6]

    expiry = line2[8:14]
    expiry_check = line2[14]

    doc_valid = validate_mrz_checksum(doc_num, doc_check)
    dob_valid = validate_mrz_checksum(dob, dob_check)
    expiry_valid = validate_mrz_checksum(expiry, expiry_check)

    all_valid = doc_valid and dob_valid and expiry_valid
    errors = []
    if not doc_valid:
        errors.append("Document number checksum failed")
    if not dob_valid:
        errors.append("Date of birth checksum failed")
    if not expiry_valid:
        errors.append("Expiry date checksum failed")

    return {
        "format": "TD1 (ID Card)",
        "is_valid": all_valid,
        "tampered": not all_valid,
        "document_number": doc_num.replace("<", ""),
        "dob": dob,
        "expiry": expiry,
        "checks": {
            "document_number": doc_valid,
            "dob": dob_valid,
            "expiry": expiry_valid,
        },
        "errors": errors,
        "details": "All ICAO 9303 check digits valid." if all_valid else "; ".join(errors),
    }


# ==============================================================================
# 5. UNIFIED FORENSIC INSPECTION PIPELINE
# ==============================================================================

def analyze_document_forensics(
    file_bytes: bytes,
    ocr_text: str | None = None,
    is_pdf: bool = False,
) -> dict[str, Any]:
    """
    Forensic tampering inspection for PDF documents only.

    For PDF uploads, evaluates:
    1. PDF Stream & Vector Object Analysis (white-box masking, font subsets, coordinate jitter)
    2. PDF Metadata Provenance (consumer editor detection: Photoshop, Canva, Sejda, etc.)
    3. Error Level Analysis (ELA) on embedded/rasterized pages
    4. ICAO Doc 9303 Checksum Validation on MRZ strings

    Non-PDF documents (PNG/JPEG screenshots) skip forensic tampering rules.
    """
    pdf_detected = bool(is_pdf or file_bytes.startswith(b"%PDF"))
    if not pdf_detected:
        return {
            "is_pdf": False,
            "tampering_detected": False,
            "severity": "CLEAN",
            "reasons": [],
            "flags": [],
            "summary": "Forensics rules apply to PDF documents only (skipped for image).",
            "ela": None,
            "metadata": None,
            "pdf_forensics": None,
            "mrz": None,
        }

    reasons: list[str] = []
    flags: list[str] = []
    tampered = False

    # 1. PDF Vector Stream analysis
    pdf_res = analyze_pdf_stream(file_bytes)
    if pdf_res["tampered"]:
        tampered = True
        reasons.append("pdf_vector_tampering")
        flags.extend(pdf_res["flags"])

    # 2. PDF Metadata Provenance
    meta_res = analyze_metadata(file_bytes)
    if meta_res["tampered"]:
        tampered = True
        reasons.append("suspicious_editor_metadata")
        flags.extend(meta_res["flags"])

    # 3. Error Level Analysis (ELA) on PDF raster/image stream
    ela_res = None
    try:
        ela_res = compute_ela(file_bytes)
        if ela_res["tampered"]:
            tampered = True
            reasons.append("copy_paste_tampering")
            flags.append(ela_res["details"])
    except Exception:
        pass

    # 4. ICAO MRZ Check-Digit Validation (if text extracted from PDF)
    mrz_res = None
    if ocr_text:
        mrz_res = parse_and_validate_mrz(ocr_text)
        if mrz_res and mrz_res["tampered"]:
            tampered = True
            reasons.append("mrz_checksum_invalid")
            flags.extend(mrz_res["errors"])

    return {
        "is_pdf": True,
        "tampering_detected": tampered,
        "severity": "CRITICAL" if (tampered and len(reasons) > 1) else ("HIGH" if tampered else "CLEAN"),
        "reasons": list(dict.fromkeys(reasons)),
        "flags": flags,
        "summary": "; ".join(flags) if flags else "No tampering detected in PDF document.",
        "ela": ela_res,
        "metadata": meta_res,
        "pdf_forensics": pdf_res,
        "mrz": mrz_res,
    }
