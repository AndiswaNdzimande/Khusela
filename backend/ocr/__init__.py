"""Khusela OCR package: local Tesseract with a Docker fallback."""

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
    "available_backends",
    "build_docker_image",
    "docker_image_available",
    "is_docker_available",
    "is_local_available",
    "local_tesseract_version",
    "run_ocr",
    "select_backend",
]
