"""E2E workflow test verifying the complete user/session/analysis pipeline."""
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


def test_full_e2e_user_and_session_flow(client):
    # 1. Register Clinician
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "username": "dr_alexander",
            "email": "alexander@biomech.org",
            "password": "Password123!",
            "role": "professional",
        },
    )
    assert reg_res.status_code == 201
    token = reg_res.json()["access_token"]
    assert token
    client.headers["Authorization"] = f"Bearer {token}"

    # 2. Verify identity via /me
    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "dr_alexander"
    assert me_res.json()["role"] == "professional"

    # 3. Create Patient / Subject
    sub_res = client.post(
        "/api/v1/subjects",
        json={"display_name": "Subject #101 - Hemiparesis Cohort"},
    )
    assert sub_res.status_code == 201
    subject_id = sub_res.json()["id"]

    # 4. List subjects
    list_res = client.get("/api/v1/subjects")
    assert list_res.status_code == 200
    assert any(s["id"] == subject_id for s in list_res.json()["items"])

    # 5. Create Assessment Session with Biomechanical Metadata
    sess_res = client.post(
        f"/api/v1/subjects/{subject_id}/sessions",
        json={
            "camera_view": "front",
            "walking_speed_ms": 1.15,
            "walking_surface": "ground",
            "height_m": 1.75,
            "mass_kg": 72.0,
            "footwear": "barefoot",
        },
    )
    assert sess_res.status_code == 201
    session_id = sess_res.json()["id"]

    # 6. Retrieve Session Details
    get_sess_res = client.get(f"/api/v1/sessions/{session_id}")
    assert get_sess_res.status_code == 200
    sess_data = get_sess_res.json()
    assert sess_data["camera_view"] == "front"
    assert sess_data["walking_speed_ms"] == 1.15

    # 7. Check Security: Unauthenticated access to protected routes
    client.headers.pop("Authorization", None)
    unauth_res = client.get("/api/v1/auth/me")
    assert unauth_res.status_code == 401

    # 8. Check Security: Invalid token
    bad_token_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid_garbage_token"},
    )
    assert bad_token_res.status_code == 401
