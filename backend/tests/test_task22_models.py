"""TASK-22: Database models – insert and read one row per model."""
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models import Check, ExpectedSale, Fingerprint, Seller

_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
_Session = sessionmaker(bind=_engine)


def setup_module():
    Base.metadata.create_all(bind=_engine)


def test_seller_insert_and_read():
    db = _Session()
    s = Seller(business_name="Thabo Sneakers", password_hash="hashed")
    db.add(s)
    db.commit()
    found = db.query(Seller).filter_by(business_name="Thabo Sneakers").first()
    assert found is not None
    assert found.id is not None
    db.close()


def test_expected_sale_insert():
    db = _Session()
    s = Seller(business_name="Naledi Hair", password_hash="x")
    db.add(s)
    db.flush()
    sale = ExpectedSale(
        seller_id=s.id,
        amount=15000,
        reference="INV-001",
        expected_at=datetime.now(timezone.utc),
    )
    db.add(sale)
    db.commit()
    assert db.query(ExpectedSale).filter_by(seller_id=s.id).count() == 1
    db.close()


def test_check_insert():
    db = _Session()
    s = Seller(business_name="Zim Grocery", password_hash="x")
    db.add(s)
    db.flush()
    chk = Check(seller_id=s.id, verdict="MATCH", reasons=[])
    db.add(chk)
    db.commit()
    assert db.query(Check).filter_by(seller_id=s.id).first().verdict == "MATCH"
    db.close()


def test_fingerprint_insert():
    db = _Session()
    s = Seller(business_name="Spaza One", password_hash="x")
    db.add(s)
    db.flush()
    chk = Check(seller_id=s.id, verdict="STOP", reasons=["duplicate_image"])
    db.add(chk)
    db.flush()
    fp = Fingerprint(seller_id=s.id, check_id=chk.id, hash="abcd1234", hash_int=12345)
    db.add(fp)
    db.commit()
    assert db.query(Fingerprint).filter_by(check_id=chk.id).first().hash == "abcd1234"
    db.close()


def test_cascade_delete_seller():
    db = _Session()
    s = Seller(business_name="Delete Me", password_hash="x")
    db.add(s)
    db.flush()
    chk = Check(seller_id=s.id, verdict="MATCH", reasons=[])
    db.add(chk)
    db.commit()
    db.delete(s)
    db.commit()
    # Check row should be gone via cascade
    assert db.query(Check).filter_by(seller_id=s.id).count() == 0
    db.close()
