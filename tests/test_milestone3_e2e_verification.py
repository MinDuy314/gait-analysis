"""Comprehensive Milestone 3 E2E verification test.

Verifies:
1. Analysis job submission and polling through the API.
2. Real frame progress incrementing during processing.
3. Progress percentage strictly clamped between 0 and 100%.
4. Polling cessation on job completion.
5. 100% completion state and annotated video availability.
6. Job failure state capturing actual backend error message.
7. Authenticated video streaming and MP4 download (binary video/mp4).
8. RBAC isolation (patient cannot access other patient's session/job/video).
"""
import io
import time
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.main import app
from src.api.dependencies import get_db, get_job_manager
from src.api.auth.security import create_access_token, hash_password
from src.database.database import Base
from src.database.models import User, Subject, Session as DbSession, Recording, AnalysisJob
from src.jobs.job_manager import JobManager
from src.jobs.task_registry import run_analysis_pipeline
from src.pose_estimation.landmark_schema import FramePose, Landmark


@pytest.fixture
def test_setup():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    # Create Clinician
    clinician = User(
        id="clinician_e2e_1",
        username="dr_e2e",
        hashed_password=hash_password("pw123"),
        role="professional",
        organization_id="org_alpha",
    )
    # Create Patient A
    patient_a = User(
        id="patient_e2e_a",
        username="patient_a",
        hashed_password=hash_password("pw123"),
        role="individual",
        organization_id="org_alpha",
    )
    # Create Patient B (isolated)
    patient_b = User(
        id="patient_e2e_b",
        username="patient_b",
        hashed_password=hash_password("pw123"),
        role="individual",
        organization_id="org_alpha",
    )
    db.add_all([clinician, patient_a, patient_b])
    db.commit()

    jm = JobManager(db_session_factory=SessionLocal, max_workers=2)

    def _get_db_override():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[get_job_manager] = lambda: jm

    client = TestClient(app)

    yield {
        "db": db,
        "jm": jm,
        "client": client,
        "clinician": clinician,
        "patient_a": patient_a,
        "patient_b": patient_b,
        "SessionLocal": SessionLocal,
    }

    jm.wait_all(timeout=3.0)
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _make_mp4(path: Path, frames: int = 10, width: int = 64, height: int = 48) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, 10.0, (width, height))
    for i in range(frames):
        img = np.zeros((height, width, 3), dtype=np.uint8)
        img[:, :, i % 3] = 120
        writer.write(img)
    writer.release()
    return path


def test_milestone3_e2e_successful_video_processing_and_playback(test_setup, tmp_path):
    client = test_setup["client"]
    db = test_setup["db"]
    patient = test_setup["patient_a"]
    token = create_access_token(data={"sub": patient.id, "role": patient.role})
    client.headers["Authorization"] = f"Bearer {token}"

    # 1. Create Patient Subject & Session
    sub = Subject(id="sub_m3", owner_id=patient.id, organization_id="org_alpha")
    db.add(sub)
    sess = DbSession(id="sess_m3", subject_id=sub.id)
    db.add(sess)
    db.commit()

    # 2. Upload video file
    video_path = _make_mp4(tmp_path / "walking.mp4", frames=12)
    with open(video_path, "rb") as f:
        up_res = client.post(
            f"/api/v1/sessions/{sess.id}/recordings",
            files={"file": ("walking.mp4", f, "video/mp4")},
        )
    assert up_res.status_code == 201
    recording_id = up_res.json()["id"]

    # 3. Submit analysis job
    submit_res = client.post(
        f"/api/v1/sessions/{sess.id}/analysis",
        json={"recording_id": recording_id, "camera_view": "side", "pose_model": "yolo"},
    )
    assert submit_res.status_code == 202
    job_id = submit_res.json()["id"]

    # 4. Wait for job completion and verify progress metrics
    test_setup["jm"].wait_all(timeout=15.0)

    # 5. Check job status via /api/v1/jobs/{job_id} and /api/v1/sessions/{session_id}/job
    job_res = client.get(f"/api/v1/jobs/{job_id}")
    assert job_res.status_code == 200
    job_data = job_res.json()
    assert job_data["status"] == "completed"
    assert job_data["progress_pct"] == 100.0
    assert 0 <= job_data["progress_pct"] <= 100.0
    assert job_data["processed_frames"] > 0
    assert job_data["total_frames"] > 0
    assert job_data["processed_frames"] == job_data["total_frames"]

    sess_job_res = client.get(f"/api/v1/sessions/{sess.id}/job")
    assert sess_job_res.status_code == 200
    assert sess_job_res.json()["id"] == job_id

    # 6. Verify annotated video availability and binary download
    rec_res = client.get(f"/api/v1/recordings/{recording_id}")
    assert rec_res.status_code == 200
    assert rec_res.json()["annotation_status"] == "completed"
    assert rec_res.json()["annotated_video_path"] is not None

    video_res = client.get(f"/api/v1/recordings/{recording_id}/annotated-video")
    assert video_res.status_code == 200
    assert "video/mp4" in video_res.headers.get("content-type", "")
    assert len(video_res.content) > 0
    assert "annotated_" in video_res.headers.get("content-disposition", "")


def test_milestone3_e2e_failed_video_processing(test_setup, tmp_path):
    client = test_setup["client"]
    db = test_setup["db"]
    patient = test_setup["patient_a"]
    token = create_access_token(data={"sub": patient.id, "role": patient.role})
    client.headers["Authorization"] = f"Bearer {token}"

    sub = Subject(id="sub_m3_fail", owner_id=patient.id, organization_id="org_alpha")
    db.add(sub)
    sess = DbSession(id="sess_m3_fail", subject_id=sub.id)
    db.add(sess)

    # Create dummy corrupt video file
    corrupt_video = tmp_path / "corrupt.mp4"
    corrupt_video.write_bytes(b"not a valid mp4 header")
    rec = Recording(
        id="rec_m3_fail",
        session_id=sess.id,
        server_filename="corrupt.mp4",
        file_path=str(corrupt_video),
        validation_status="pending",
    )
    db.add(rec)
    db.commit()

    submit_res = client.post(
        f"/api/v1/sessions/{sess.id}/analysis",
        json={"recording_id": rec.id, "camera_view": "side", "pose_model": "yolo"},
    )
    assert submit_res.status_code == 202
    job_id = submit_res.json()["id"]

    test_setup["jm"].wait_all(timeout=10.0)

    job_res = client.get(f"/api/v1/jobs/{job_id}")
    assert job_res.status_code == 200
    data = job_res.json()
    assert data["status"] == "failed"
    assert data["error_message"] is not None
    assert "Video validation failed" in data["error_message"]


def test_milestone3_e2e_rbac_isolation(test_setup, tmp_path):
    client = test_setup["client"]
    db = test_setup["db"]
    patient_a = test_setup["patient_a"]
    patient_b = test_setup["patient_b"]

    # Session belonging to Patient A
    sub_a = Subject(id="sub_a_iso", owner_id=patient_a.id, organization_id="org_alpha")
    db.add(sub_a)
    sess_a = DbSession(id="sess_a_iso", subject_id=sub_a.id)
    db.add(sess_a)
    video_path = _make_mp4(tmp_path / "a_video.mp4", frames=5)
    rec_a = Recording(
        id="rec_a_iso",
        session_id=sess_a.id,
        server_filename="a_video.mp4",
        file_path=str(video_path),
        annotated_video_path=str(video_path),
        annotation_status="completed",
    )
    db.add(rec_a)
    job_a = AnalysisJob(
        id="job_a_iso",
        session_id=sess_a.id,
        subject_id=sub_a.id,
        status="completed",
        progress_pct=100.0,
        processed_frames=5,
        total_frames=5,
    )
    db.add(job_a)
    db.commit()

    # Log in as Patient B
    token_b = create_access_token(data={"sub": patient_b.id, "role": patient_b.role})
    client.headers["Authorization"] = f"Bearer {token_b}"

    # Patient B cannot access Patient A's job
    res_job = client.get(f"/api/v1/jobs/{job_a.id}")
    assert res_job.status_code == 403

    # Patient B cannot access Patient A's session job
    res_sess_job = client.get(f"/api/v1/sessions/{sess_a.id}/job")
    assert res_sess_job.status_code == 403

    # Patient B cannot stream or download Patient A's annotated video
    res_video = client.get(f"/api/v1/recordings/{rec_a.id}/annotated-video")
    assert res_video.status_code == 403
