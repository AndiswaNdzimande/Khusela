from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.auth import hash_password  # noqa: E402
from app.config import SEED_PASSWORD  # noqa: E402
from app.db.database import SessionLocal, init_db  # noqa: E402
from app.db.models import Seller  # noqa: E402

DEFAULT_SELLERS = [
    ("seller_a", "Thabo Sneakers"),
    ("seller_b", "Naledi Beauty Hub"),
    ("seller_c", "Mama Zodwa Spaza"),
]


def load_sellers() -> list[tuple[str, str]]:
    csv_path = ROOT / "scripts" / "data" / "sellers.csv"
    if not csv_path.exists():
        return DEFAULT_SELLERS
    rows: list[tuple[str, str]] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rows.append((row["seller_id"], row["business_name"]))
    return rows or DEFAULT_SELLERS


def main() -> None:
    init_db()
    db = SessionLocal()
    created = 0
    try:
        password_hash = hash_password(SEED_PASSWORD)
        for seller_id, business_name in load_sellers():
            existing = db.query(Seller).filter(Seller.business_name == business_name).first()
            if existing:
                continue
            db.add(Seller(id=seller_id, business_name=business_name, password_hash=password_hash))
            created += 1
        db.commit()
    finally:
        db.close()
    print(f"Seeded {created} seller(s). Dev password: {SEED_PASSWORD}")


if __name__ == "__main__":
    main()
