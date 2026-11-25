"""Tests for Milestone 6: API endpoints."""
import pytest
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.database.database import Base
from src.database import models  # noqa
from src.api.dependencies import get_db, get_storage, get_job_manager
from src.jobs.job_manager import JobManager
from src.storage.file_storage import FileStorage
from src.api.main import app


@pytest.fixture
def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        storage = FileStorage(storage_root=Path(tmpdir) / "uploads")
        test_jm = JobManager(db_session_factory=TestingSessionLocal, max_workers=2)

        def override_db():
            db = TestingSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_storage] = lambda: storage
        app.dependency_overrides[get_job_manager] = lambda: test_jm

        with TestClient(app) as c:
            yield c

        test_jm.wait_all(timeout=5.0)
        app.dependency_overrides.clear()
        engine.dispose()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_create_subject(client):
    r = client.post("/api/v1/subjects", json={"display_name": "Test Subject"})
    assert r.status_code == 201
    data = r.json()
    assert "id" in data


def test_list_subjects(client):
    client.post("/api/v1/subjects", json={})
    r = client.get("/api/v1/subjects")
    assert r.status_code == 200
    assert "items" in r.json()


def test_get_subject_not_found(client):
    r = client.get("/api/v1/subjects/nonexistent")
    assert r.status_code == 404


def test_create_session(client):
    sub = client.post("/api/v1/subjects", json={}).json()
    r = client.post(f"/api/v1/subjects/{sub['id']}/sessions", json={"camera_view": "side"})
    assert r.status_code == 201
    assert r.json()["subject_id"] == sub["id"]


def test_list_sessions(client):
    sub = client.post("/api/v1/subjects", json={}).json()
    client.post(f"/api/v1/subjects/{sub['id']}/sessions", json={})
    r = client.get(f"/api/v1/subjects/{sub['id']}/sessions")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1


def test_get_session_not_found(client):
    r = client.get("/api/v1/sessions/nonexistent")
    assert r.status_code == 404


def test_delete_subject(client):
    sub = client.post("/api/v1/subjects", json={}).json()
    r = client.delete(f"/api/v1/subjects/{sub['id']}")
    assert r.status_code == 204
    r2 = client.get(f"/api/v1/subjects/{sub['id']}")
    assert r2.status_code == 404


def test_generate_report(client):
    sub = client.post("/api/v1/subjects", json={}).json()
    sess = client.post(f"/api/v1/subjects/{sub['id']}/sessions", json={"camera_view": "side"}).json()
    r = client.post(f"/api/v1/sessions/{sess['id']}/reports", json={"report_type": "individual"})
    assert r.status_code == 201
    assert r.json()["report_type"] == "individual"


def test_generate_professional_report(client):
    sub = client.post("/api/v1/subjects", json={}).json()
    sess = client.post(f"/api/v1/subjects/{sub['id']}/sessions", json={}).json()
    r = client.post(f"/api/v1/sessions/{sess['id']}/reports", json={"report_type": "professional"})
    assert r.status_code == 201


def test_submit_analysis_job(client):
    sub = client.post("/api/v1/subjects", json={}).json()
    sess = client.post(f"/api/v1/subjects/{sub['id']}/sessions", json={"camera_view": "side"}).json()
    r = client.post(f"/api/v1/sessions/{sess['id']}/analysis", json={"camera_view": "side"})
    assert r.status_code == 202
    assert r.json()["status"] == "queued"


def test_get_job(client):
    sub = client.post("/api/v1/subjects", json={}).json()
    sess = client.post(f"/api/v1/subjects/{sub['id']}/sessions", json={}).json()
    job = client.post(f"/api/v1/sessions/{sess['id']}/analysis", json={}).json()
    r = client.get(f"/api/v1/jobs/{job['id']}")
    assert r.status_code == 200


def test_get_job_not_found(client):
    r = client.get("/api/v1/jobs/nonexistent")
    assert r.status_code == 404
