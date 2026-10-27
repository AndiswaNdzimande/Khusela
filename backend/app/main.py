"""
TASK-21: FastAPI application entry point.
Start with:  uvicorn app.main:app --reload   (from the backend/ directory)

v5 fixes applied:
  N3: routers now mounted under BOTH /auth + /check AND /api/auth + /api/check
      so the UI (which posts to /api/...) and the contract both work.
  N4: HTTPBearer(auto_error=False) so a missing token returns 401, not 403.
  N6: startup self-test calls _pipeline_self_test() and shows result in /health.
  LOW: placeholder JWT secret ('replace_with_a_long_random_secret') is rejected.
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
_PLACEHOLDER = "replace_with_a_long_random_secret"

if not _JWT_SECRET:
    logger.error(
        "JWT_SECRET_KEY is not set. "
        "Copy backend/.env.example to backend/.env and set a value, then restart."
    )
    sys.exit(1)

if _JWT_SECRET == _PLACEHOLDER:
    logger.error(
        "JWT_SECRET_KEY is still the placeholder value from .env.example. "
        "Generate a real secret: python -c \"import secrets; print(secrets.token_hex(32))\""
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Application imports (after env check so auth.py reads SECRET_KEY safely)
# ---------------------------------------------------------------------------
from app.api.auth import router as auth_router
from app.db.database import Base, engine
from app.routers.check import router as check_router, _pipeline_self_test

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Khusela API",
    description="Proof-of-payment verification for informal sellers.",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# CORS — restrict to frontend origin(s) via ALLOWED_ORIGINS env var
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
# N3 fix: mount under both bare paths AND /api prefix so the UI and the
# contract work regardless of which prefix is used.
# ---------------------------------------------------------------------------
app.include_router(auth_router)                          # /auth/register, /auth/login
app.include_router(auth_router, prefix="/api")           # /api/auth/register, /api/auth/login
app.include_router(check_router)                         # /health, /check
app.include_router(check_router, prefix="/api")          # /api/health, /api/check

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------
_scheduler = None


@app.on_event("startup")
def on_startup():
    global _scheduler

    # Scheduler only if raw-file storage is explicitly enabled
    if os.getenv("START_SCHEDULER", "0") == "1":
        from app.scheduler import start_scheduler
        _scheduler = start_scheduler()
        logger.info("Raw-file deletion scheduler started.")
    else:
        logger.info("Deletion scheduler OFF (START_SCHEDULER != 1).")

    # N6 fix: self-test the pipeline with a real call, not just an import check
    pipeline_ok = _pipeline_self_test()
    if pipeline_ok:
        logger.info("Pipeline self-test: REAL — integration.check_payment is callable.")
    else:
        logger.warning(
            "Pipeline self-test: STUB — /check will return engine_unavailable. "
            "Merge TASK-05 branch and fix check_payment kwargs to get real verdicts."
        )

    logger.info("Khusela API started. /health shows pipeline status.")


@app.on_event("shutdown")
def on_shutdown():
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    logger.info("Khusela API shut down.")
