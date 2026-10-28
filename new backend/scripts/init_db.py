from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import DATABASE_URL  # noqa: E402
from app.db.database import init_db  # noqa: E402


def main() -> None:
    init_db()
    print(f"Database ready: {DATABASE_URL}")


if __name__ == "__main__":
    main()
