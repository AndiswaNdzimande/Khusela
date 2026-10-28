from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("VERIPOP_AUTH_SECRET", "test-secret-that-is-long-enough-to-be-32-bytes")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-that-is-long-enough-to-be-32-bytes")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("VERIPOP_DATA_DIR", "./test-data")

import pytest
from fastapi.testclient import TestClient

from app import auth as auth_mod
from app.db.database import Base, engine
from app.db import models as _models  # noqa: F401
from app.main import app
from app import main


@pytest.fixture(autouse=True)
def fresh_db(tmp_path: Path) -> None:
    auth_mod.configure_auth_secret("test-secret-that-is-long-enough-to-be-32-bytes")
    main.AUTH_SECRET = "test-secret-that-is-long-enough-to-be-32-bytes"
    main.DATA_DIR = tmp_path
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    for path in tmp_path.glob("*"):
        if path.is_file():
            path.unlink()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
