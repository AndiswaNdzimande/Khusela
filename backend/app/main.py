"""
TASK-21: FastAPI application entry point.
Start with:  uvicorn app.main:app --reload   (from the backend/ directory)

Bug fixes (v4 report):
  Bug 8: JWT_SECRET_KEY used os.environ[] at import time, crashing before the
         app could start or show a helpful message. Moved to a startup check
         that raises a clear RuntimeError if the key is missing.
  Bug 7: Scheduler is kept available but NOT started by default, because
         /check no longer writes raw files to disk. Set START_SCHEDULER=1 in
         .env to enable it for teams that choose to store files.
"""
import logging
import os
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Validate required env vars before anything else loads
# ---------------------------------------------------------------------------
_JWT_SECRET = os.getenv("JWT_SECRET_KEY", "")
if not _JWT_SECRET:
    logger.error(
        "JWT_SECRET_KEY is not set. "
        "Copy backend/.env.example to backend/.env and set a value, then restart."
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Application imports (after env check so auth.py can read SECRET_KEY safely)
# ---------------------------------------------------------------------------
from app.api.auth import router as auth_router
from app.db.database import Base, engine
from app.routers.check import router as check_router

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Khusela API",
    description="Proof-of-payment verification for informal sellers.",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# CORS – restrict to frontend origin(s) via ALLOWED_ORIGINS env var
# ---------------------------------------------------------------------------
_origins_env = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = (
    [o.strip() for o in _origins_env.split(",") if o.strip()]
    or ["http://localhost:5173"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth_router)
app.include_router(check_router)

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
_scheduler = None


@app.on_event("startup")
def on_startup():
    global _scheduler
    # Scheduler only started if raw-file storage is explicitly enabled
    if os.getenv("START_SCHEDULER", "0") == "1":
        from app.scheduler import start_scheduler
        _scheduler = start_scheduler()
        logger.info("Raw-file deletion scheduler started.")
    else:
        logger.info(
            "Deletion scheduler is OFF (START_SCHEDULER != 1). "
            "/check does not store raw files — no cleanup needed."
        )

    # Log which pieces are real vs stand-in (acceptance check from report section 5)
    _log_integration_status()
    logger.info("Khusela API started.")


@app.on_event("shutdown")
def on_shutdown():
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    logger.info("Khusela API shut down.")


def _log_integration_status():
    """Log whether each pipeline piece is real or a stand-in."""
    pieces = {
        "integration": "integration",
        "ocr": "ocr",
        "engine": "engine",
    }
    for name, module in pieces.items():
        try:
            __import__(module)
            logger.info("Pipeline piece '%s': REAL", name)
        except ImportError:
            logger.warning("Pipeline piece '%s': STAND-IN (ImportError)", name)
