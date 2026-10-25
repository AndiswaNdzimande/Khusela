"""TASK-26: Raw-image deletion job."""
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Check, Fingerprint, Seller
from app.scheduler import delete_expired_raw_files

# Point the scheduler at an in-memory DB for this test module
import app.scheduler as _sched_mod

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
_Session = sessionmaker(bind=_engine)


def setup_module():
    Base.metadata.create_all(bind=_engine)
    # Patch SessionLocal inside the scheduler module
    _sched_mod.SessionLocal = _Session


def _add_check(db, seller, path, uploaded_at):
    c = Check(
        seller_id=seller.id,
        verdict="MATCH",
        reasons=[],
        raw_file_path=path,
        raw_file_uploaded_at=uploaded_at,
    )
    db.add(c)
    db.flush()
    return c


def test_expired_file_deleted():
    db = _Session()
    seller = Seller(business_name=f"S-{uuid.uuid4()}", password_hash="x")
    db.add(seller)
    db.flush()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
        f.write(b"fake image")
        path = f.name

    old_time = datetime.now(timezone.utc) - timedelta(hours=25)
    _add_check(db, seller, path, old_time)
    db.commit()
    db.close()

    delete_expired_raw_files()

    assert not Path(path).exists(), "Expired file should have been deleted"


def test_recent_file_kept():
    db = _Session()
    seller = Seller(business_name=f"S-{uuid.uuid4()}", password_hash="x")
    db.add(seller)
    db.flush()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
        f.write(b"recent image")
        path = f.name

    recent_time = datetime.now(timezone.utc) - timedelta(hours=1)
    _add_check(db, seller, path, recent_time)
    db.commit()
    db.close()

    delete_expired_raw_files()

    assert Path(path).exists(), "Recent file should NOT have been deleted"
    Path(path).unlink(missing_ok=True)  # cleanup


def test_fingerprint_rows_survive_deletion():
    db = _Session()
    seller = Seller(business_name=f"S-{uuid.uuid4()}", password_hash="x")
    db.add(seller)
    db.flush()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
        f.write(b"data")
        path = f.name

    old_time = datetime.now(timezone.utc) - timedelta(hours=25)
    chk = _add_check(db, seller, path, old_time)
    fp = Fingerprint(seller_id=seller.id, check_id=chk.id, hash="aabbcc", hash_int=1)
    db.add(fp)
    db.commit()
    check_id = chk.id
    db.close()

    delete_expired_raw_files()

    db2 = _Session()
    assert db2.query(Fingerprint).filter_by(check_id=check_id).count() == 1, \
        "Fingerprint row must survive raw file deletion"
    db2.close()
