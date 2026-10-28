from datetime import UTC, datetime

from app.db.database import SessionLocal
from app.db.models import Check, ExpectedSale, Fingerprint, Seller


def test_seller_insert_and_read() -> None:
    db = SessionLocal()
    seller = Seller(business_name="Thabo Sneakers", password_hash="hashed")
    db.add(seller)
    db.commit()
    found = db.query(Seller).filter_by(business_name="Thabo Sneakers").first()
    assert found is not None
    assert found.id is not None
    db.close()


def test_expected_sale_insert() -> None:
    db = SessionLocal()
    seller = Seller(business_name="Naledi Hair", password_hash="x")
    db.add(seller)
    db.flush()
    db.add(
        ExpectedSale(
            seller_id=seller.id,
            amount=15000,
            reference="INV-001",
            expected_at=datetime.now(UTC),
        )
    )
    db.commit()
    assert db.query(ExpectedSale).filter_by(seller_id=seller.id).count() == 1
    db.close()


def test_check_and_fingerprint_insert() -> None:
    db = SessionLocal()
    seller = Seller(business_name="Spaza One", password_hash="x")
    db.add(seller)
    db.flush()
    check = Check(seller_id=seller.id, verdict="STOP", reasons=["duplicate_image"])
    db.add(check)
    db.flush()
    db.add(Fingerprint(seller_id=seller.id, check_id=check.id, hash="abcd1234", hash_int=12345, hash_algo="sha256"))
    db.commit()
    assert db.query(Fingerprint).filter_by(check_id=check.id).first().hash == "abcd1234"
    db.close()


def test_cascade_delete_seller() -> None:
    db = SessionLocal()
    seller = Seller(business_name="Delete Me", password_hash="x")
    db.add(seller)
    db.flush()
    db.add(Check(seller_id=seller.id, verdict="MATCH", reasons=[]))
    db.commit()
    seller_id = seller.id
    db.delete(seller)
    db.commit()
    assert db.query(Check).filter_by(seller_id=seller_id).count() == 0
    db.close()
