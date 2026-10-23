"""Khusela OCR package: local Tesseract with a Docker fallback."""

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
    "OcrError",
    "OcrResult",
    "OcrUnavailableError",
    "PreprocessConfig",
    "available_backends",
    "build_docker_image",
    "docker_image_available",
    "is_docker_available",
    "is_local_available",
    "local_tesseract_version",
    "preprocess_bytes",
    "preprocess_image",
    "resize_for_ocr",
    "run_ocr",
    "select_backend",
    "threshold_image",
    "to_grayscale",
]
