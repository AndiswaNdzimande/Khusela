"""Shared pytest fixtures."""
import os

# Must be set before any app import (bug 8 fix: auth.py reads at import time)
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_khusela.db")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite:///./test_khusela.db"

engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def fresh_db():
    """Drop and recreate all tables before each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def registered_seller(client):
    """Register a seller and return (business_name, password, token)."""
    name, pw = "Test Seller", "password123"
    client.post("/auth/register", json={"business_name": name, "password": pw})
    resp = client.post("/auth/login", json={"business_name": name, "password": pw})
    token = resp.json()["access_token"]
    return name, pw, token
