"""Dependency and database driver check for the Khusela backend."""
import sys

checks = [
    # (import_name, display_name, required)
    ("sqlalchemy",   "sqlalchemy (ORM/DB layer)",        True),
    ("sqlite3",      "sqlite3 (built-in, default DB)",   True),
    ("psycopg2",     "psycopg2 (PostgreSQL - optional)", False),
    ("dotenv",       "python-dotenv",                    True),
    ("fastapi",      "fastapi",                          True),
    ("uvicorn",      "uvicorn",                          True),
    ("pydantic",     "pydantic",                         True),
    ("multipart",    "python-multipart",                 True),
    ("PIL",          "Pillow (image processing)",        True),
    ("numpy",        "numpy",                            True),
    ("pytesseract",  "pytesseract (OCR)",                False),
    ("apscheduler",  "apscheduler (scheduler)",          True),
    ("httpx",        "httpx (HTTP client/tests)",        True),
    ("pytest",       "pytest",                           True),
]

print(f"Python: {sys.version}")
print(f"Executable: {sys.executable}")
print("-" * 60)

missing_required = []
for module, label, required in checks:
    try:
        mod = __import__(module)
        version = getattr(mod, "__version__", getattr(mod, "sqlite_version", "OK"))
        print(f"  [OK]      {label}: {version}")
    except ImportError:
        status = "MISSING (required)" if required else "not installed (optional)"
        marker = "  [MISSING]" if required else "  [opt]   "
        print(f"{marker} {label}: {status}")
        if required:
            missing_required.append(label)

print("-" * 60)

# Also verify the DB file itself
import os
from pathlib import Path
db_url = os.getenv("DATABASE_URL", "sqlite:///./khusela.db")
print(f"\nDATABASE_URL: {db_url}")
if db_url.startswith("sqlite:///"):
    db_path_str = db_url.replace("sqlite:///", "")
    db_path = Path(db_path_str)
    if not db_path.is_absolute():
        db_path = Path(__file__).resolve().parents[1] / db_path
    if db_path.exists():
        size_kb = db_path.stat().st_size / 1024
        print(f"SQLite file:  {db_path}  ({size_kb:.1f} KB)  [EXISTS]")
        # Try to open and list tables
        try:
            import sqlite3 as _sqlite3
            conn = _sqlite3.connect(str(db_path))
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            conn.close()
            if tables:
                print(f"Tables found: {', '.join(t[0] for t in tables)}")
            else:
                print("Tables found: (none — run scripts/init_db.py)")
        except Exception as e:
            print(f"Could not inspect DB: {e}")
    else:
        print(f"SQLite file:  {db_path}  [NOT CREATED YET — run scripts/init_db.py]")

print()
if missing_required:
    print(f"ACTION NEEDED: {len(missing_required)} required package(s) missing.")
    print("Run:  pip install -r requirements.txt")
    sys.exit(1)
else:
    print("All required packages are installed.")
