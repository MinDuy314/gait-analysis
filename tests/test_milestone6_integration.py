"""End-to-end integration test: subject \u2192 session \u2192 analysis \u2192 report."""
import pytest
import time
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
        SL = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        storage = FileStorage(storage_root=Path(tmpdir) / "uploads")
        test_jm = JobManager(db_session_factory=SL, max_workers=2)

        with SL() as db:
            import uuid
            from src.database import models
            from src.api.auth.security import hash_password, create_access_token
            u = models.User(
                id=str(uuid.uuid4()),
                username="test_clinician_integ",
                hashed_password=hash_password("Pass@123"),
                role="professional",
                organization_id="default_org",
                is_active=True,
            )
            db.add(u)
            db.commit()
            token = create_access_token(data={"sub": u.id, "role": u.role})

        def override_db():
            db = SL()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_storage] = lambda: storage
        app.dependency_overrides[get_job_manager] = lambda: test_jm

        with TestClient(app) as c:
            c.headers["Authorization"] = f"Bearer {token}"
            yield c

        test_jm.wait_all(timeout=5.0)
        app.dependency_overrides.clear()
        engine.dispose()


def test_end_to_end_workflow(client):
    # 1. Create subject
    sub = client.post("/api/v1/subjects", json={"display_name": "Integration Test Subject"}).json()
    assert "id" in sub
    subject_id = sub["id"]

    # 2. Create session
    sess = client.post(f"/api/v1/subjects/{subject_id}/sessions", json={
        "camera_view": "side",
        "walking_speed_ms": 1.2,
        "walking_surface": "level",
    }).json()
    session_id = sess["id"]

    # 3. Submit analysis job
    job = client.post(f"/api/v1/sessions/{session_id}/analysis", json={"camera_view": "side"}).json()
    job_id = job["id"]
    assert job["status"] == "queued"

    # 4. Poll job status
    for _ in range(40):
        time.sleep(0.3)
        status_r = client.get(f"/api/v1/jobs/{job_id}")
        if status_r.json()["status"] in ("completed", "failed", "partially_completed"):
            break

    final_status = client.get(f"/api/v1/jobs/{job_id}").json()
    assert final_status["status"] in ("completed", "partially_completed")

    # 5. Generate individual report
    r_ind = client.post(f"/api/v1/sessions/{session_id}/reports", json={"report_type": "individual"})
    assert r_ind.status_code == 201
    report_id = r_ind.json()["id"]

    # 6. Generate professional report
    r_pro = client.post(f"/api/v1/sessions/{session_id}/reports", json={"report_type": "professional"})
    assert r_pro.status_code == 201

    # 7. Retrieve report
    r_get = client.get(f"/api/v1/reports/{report_id}")
    assert r_get.status_code == 200

    # 8. Verify subject exists
    s_get = client.get(f"/api/v1/subjects/{subject_id}")
    assert s_get.status_code == 200

    # 9. Verify sessions listed
    slist = client.get(f"/api/v1/subjects/{subject_id}/sessions")
    assert len(slist.json()["items"]) == 1
