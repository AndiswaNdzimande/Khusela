"""
TASK-21: FastAPI application entry point.
Start with:  uvicorn app.main:app --reload   (from the backend/ directory)
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.db.database import Base, engine
from app.routers.check import router as check_router
from app.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create all tables on startup (use Alembic for schema migrations in production)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Khusela API",
    description="Proof-of-payment verification for informal sellers.",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# CORS – restrict origins in production via ALLOWED_ORIGINS env var
# ---------------------------------------------------------------------------
import os
_origins_env = os.getenv("ALLOWED_ORIGINS", "")
allowed_origins = [o.strip() for o in _origins_env.split(",") if o.strip()] or ["http://localhost:5173"]

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
# Lifecycle – start/stop the deletion scheduler
# ---------------------------------------------------------------------------
_scheduler = None


@app.on_event("startup")
def on_startup():
    global _scheduler
    _scheduler = start_scheduler()
    logger.info("Khusela API started.")


@app.on_event("shutdown")
def on_shutdown():
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    logger.info("Khusela API shut down.")
