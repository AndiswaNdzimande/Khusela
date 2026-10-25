"""
TASK-26: 24-hour raw-image deletion scheduled job.

Behaviour:
  - Runs on a fixed interval (default every 15 minutes).
  - Deletes raw files whose upload timestamp is older than the retention window.
  - Fingerprint and Check rows are kept; only the file on disk is removed.
  - Idempotent: safe to run multiple times; already-missing files are silently skipped.
  - Logs the count of deleted files. Never logs file contents or seller data.
  - A job failure never crashes the API (exceptions are caught and logged).

Configuration (environment variables):
  RAW_IMAGE_RETENTION_HOURS   default 24
  DELETION_JOB_INTERVAL_MINUTES  default 15
  RAW_UPLOAD_DIR              default ./uploads/raw
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import Check

logger = logging.getLogger(__name__)

RETENTION_HOURS = int(os.getenv("RAW_IMAGE_RETENTION_HOURS", "24"))
JOB_INTERVAL_MINUTES = int(os.getenv("DELETION_JOB_INTERVAL_MINUTES", "15"))
RAW_UPLOAD_DIR = Path(os.getenv("RAW_UPLOAD_DIR", "./uploads/raw"))


def delete_expired_raw_files() -> None:
    """
    Core deletion logic. Called by APScheduler.
    Finds Check rows whose raw_file_path is set and raw_file_uploaded_at is
    older than RETENTION_HOURS, deletes the file from disk, then clears the
    path column so the job skips it on the next run.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=RETENTION_HOURS)
    db: Session = SessionLocal()
    deleted_count = 0
    try:
        expired = (
            db.query(Check)
            .filter(Check.raw_file_path.isnot(None))
            .filter(Check.raw_file_uploaded_at <= cutoff)
            .all()
        )

        for check in expired:
            file_path = Path(check.raw_file_path)
            try:
                if file_path.exists():
                    file_path.unlink()
                    deleted_count += 1
            except OSError as exc:
                # Log but continue – do not let one bad file stop the whole run
                logger.warning("Could not delete %s: %s", file_path.name, exc)

            # Clear the path column regardless of whether the file existed
            check.raw_file_path = None
            check.raw_file_uploaded_at = None

        db.commit()
        logger.info("Deletion job: removed %d expired raw file(s).", deleted_count)

    except Exception as exc:  # noqa: BLE001
        logger.exception("Deletion job failed: %s", exc)
        db.rollback()
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    """
    Create and start the APScheduler background scheduler.
    Returns the scheduler so the caller can shut it down on app teardown.
    """
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        delete_expired_raw_files,
        trigger="interval",
        minutes=JOB_INTERVAL_MINUTES,
        id="raw_image_deletion",
        replace_existing=True,
        misfire_grace_time=60,
    )
    scheduler.start()
    logger.info(
        "Deletion scheduler started (interval=%d min, retention=%d h).",
        JOB_INTERVAL_MINUTES,
        RETENTION_HOURS,
    )
    return scheduler
