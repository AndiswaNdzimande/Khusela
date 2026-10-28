from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


def _int_env(name: str, default: str) -> int:
    return int(os.getenv(name, default))


APP_NAME = os.getenv("APP_NAME", "Khusela")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./khusela.db")
DATA_DIR = Path(os.getenv("VERIPOP_DATA_DIR", os.getenv("RAW_UPLOAD_DIR", "./data")))
AUTH_SECRET = os.getenv("VERIPOP_AUTH_SECRET") or os.getenv("JWT_SECRET_KEY", "")
ACCESS_TOKEN_TTL_MINUTES = _int_env("ACCESS_TOKEN_TTL_MINUTES", os.getenv("JWT_EXPIRE_MINUTES", "60"))
MAX_UPLOAD_BYTES = _int_env("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))
MAX_IMAGE_PIXELS = _int_env("MAX_IMAGE_PIXELS", "40000000")
MAX_PDF_PAGES = _int_env("MAX_PDF_PAGES", "30")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if origin.strip()
]
SEED_PASSWORD = os.getenv("KHUSELA_SEED_PASSWORD", "khusela-dev-password")

# Privacy scheduler
RAW_IMAGE_RETENTION_HOURS = _int_env("RAW_IMAGE_RETENTION_HOURS", "24")
DELETION_JOB_INTERVAL_MINUTES = _int_env("DELETION_JOB_INTERVAL_MINUTES", "15")

# OCR backend selection: "auto" | "local" | "docker"
OCR_BACKEND = os.getenv("KHUSELA_OCR_BACKEND", "auto")
# Set to "1" to start the file-deletion scheduler on startup.
# Only needed if raw file storage is enabled; the scheduler is off by default.
START_SCHEDULER = os.getenv("START_SCHEDULER", "0") == "1"
