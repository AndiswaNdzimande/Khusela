"""Khusela OCR package: local Tesseract with a Docker fallback."""

from .confidence import (
    LOW_CONFIDENCE_THRESHOLD,
    RELIABLE_CONFIDENCE_THRESHOLD,
    ConfidenceScore,
    compute_confidence,
    confidence_label,
)
from .extract import (
    ExtractedFields,
    extract_amount,
    extract_fields,
    extract_recipient,
    extract_reference,
    parse_amount,
)
from .preprocess import (
    PreprocessConfig,
    preprocess_bytes,
    preprocess_image,
    resize_for_ocr,
    threshold_image,
    to_grayscale,
)
from .tesseract_engine import (
    OcrError,
    OcrResult,
    OcrUnavailableError,
    available_backends,
    build_docker_image,
    docker_image_available,
    is_docker_available,
    is_local_available,
    local_tesseract_version,
    run_ocr,
    select_backend,
)

__all__ = [
    "ExtractedFields",
    "LOW_CONFIDENCE_THRESHOLD",
    "OcrError",
    "OcrResult",
    "OcrUnavailableError",
    "PreprocessConfig",
    "RELIABLE_CONFIDENCE_THRESHOLD",
    "ConfidenceScore",
    "available_backends",
    "build_docker_image",
    "compute_confidence",
    "confidence_label",
    "docker_image_available",
    "extract_amount",
    "extract_fields",
    "extract_recipient",
    "extract_reference",
    "is_docker_available",
    "is_local_available",
    "local_tesseract_version",
    "parse_amount",
    "preprocess_bytes",
    "preprocess_image",
    "resize_for_ocr",
    "run_ocr",
    "select_backend",
    "threshold_image",
    "to_grayscale",
]
