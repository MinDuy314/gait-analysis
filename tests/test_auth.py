"""Tests for JWT authentication, registration, login, and authorization."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.main import app
from src.api.dependencies import get_db
from src.database.database import Base
from src.database import models  # noqa


@pytest.fixture(scope="function")
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture(scope="function")
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(scope="function")
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_register_success(client):
    res = client.post(
        "/api/v1/auth/register",
        json={
            "username": "clinician_jane",
            "email": "jane@example.com",
            "password": "StrongPassword123!",
            "role": "professional",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["username"] == "clinician_jane"
    assert data["role"] == "professional"


def test_register_invalid_role(client):
    res = client.post(
        "/api/v1/auth/register",
        json={
            "username": "bad_role_user",
            "password": "password123",
            "role": "superman",
        },
    )
    assert res.status_code == 400


def test_register_duplicate_username(client):
    payload = {
        "username": "duplicate_user",
        "password": "password123",
        "role": "individual",
    }
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409


def test_login_success_and_me(client):
    # Register first
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "auth_test_user",
            "password": "SecretPassword123",
            "role": "administrator",
        },
    )

    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "auth_test_user", "password": "SecretPassword123"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    assert token

    # Access /me with token
    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["username"] == "auth_test_user"
    assert me_data["role"] == "administrator"
    assert me_data["is_active"] is True


def test_login_wrong_password(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "wrong_pwd_user",
            "password": "CorrectPassword123",
            "role": "individual",
        },
    )

    res = client.post(
        "/api/v1/auth/login",
        json={"username": "wrong_pwd_user", "password": "WrongPassword!"},
    )
    assert res.status_code == 401


def test_me_unauthorized_without_token(client):
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
