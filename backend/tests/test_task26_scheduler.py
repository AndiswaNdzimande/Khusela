"""
TASK-26: Raw-image deletion scheduled job.
Note: /check no longer stores raw files by default (bug 7 fix).
The scheduler is still tested independently for teams that enable storage.
"""
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Check, Fingerprint, Seller
from app.scheduler import delete_expired_raw_files
import app.scheduler as _sched_mod

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
_Session = sessionmaker(bind=_engine)


def setup_module():
    Base.metadata.create_all(bind=_engine)
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
    s = Seller(business_name=str(uuid.uuid4()), password_hash="x")
    db.add(s)
    db.flush()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
        f.write(b"old")
        path = f.name
    old = datetime.now(timezone.utc) - timedelta(hours=25)
    _add_check(db, s, path, old)
    db.commit()
    db.close()

    delete_expired_raw_files()
    assert not Path(path).exists()


def test_recent_file_kept():
    db = _Session()
    s = Seller(business_name=str(uuid.uuid4()), password_hash="x")
    db.add(s)
    db.flush()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
        f.write(b"new")
        path = f.name
    recent = datetime.now(timezone.utc) - timedelta(hours=1)
    _add_check(db, s, path, recent)
    db.commit()
    db.close()

    delete_expired_raw_files()
    assert Path(path).exists()
    Path(path).unlink(missing_ok=True)


def test_fingerprint_rows_survive():
    db = _Session()
    s = Seller(business_name=str(uuid.uuid4()), password_hash="x")
    db.add(s)
    db.flush()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:
        f.write(b"data")
        path = f.name
    old = datetime.now(timezone.utc) - timedelta(hours=25)
    chk = _add_check(db, s, path, old)
    fp = Fingerprint(seller_id=s.id, check_id=chk.id, hash="aabbcc", hash_int=1)
    db.add(fp)
    db.commit()
    check_id = chk.id
    db.close()

    delete_expired_raw_files()

    db2 = _Session()
    assert db2.query(Fingerprint).filter_by(check_id=check_id).count() == 1
    db2.close()
