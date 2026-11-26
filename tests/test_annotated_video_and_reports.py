"""Regression tests for:
Issue 1: Annotated video generation, file verification, failure handling, and retry persistence.
Issue 2: Report generation, storage, download in Markdown and HTML, and RBAC enforcement.
"""
from __future__ import annotations

import tempfile
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
from src.database.models import User, Subject, Session as DbSession, Recording, AnalysisJob, AssessmentRecord, ReportRecord
from src.jobs.job_manager import JobManager
from src.jobs.task_registry import run_analysis_pipeline
from src.core.exceptions import VideoAnnotationError


@pytest.fixture
def fixture_setup():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    # Clinician
    clinician = User(
        id=str(uuid.uuid4()),
        username="dr_report_tester",
        hashed_password=hash_password("password"),
        role="professional",
        organization_id="org_med",
    )
    # Patient A
    patient_a = User(
        id=str(uuid.uuid4()),
        username="patient_alice",
        hashed_password=hash_password("password"),
        role="individual",
        organization_id="org_med",
    )
    # Patient B
    patient_b = User(
        id=str(uuid.uuid4()),
        username="patient_bob",
        hashed_password=hash_password("password"),
        role="individual",
        organization_id="org_med",
    )
    db.add_all([clinician, patient_a, patient_b])
    db.commit()

    jm = JobManager(db_session_factory=SessionLocal, max_workers=2)

    def _get_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
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

    jm.wait_all(timeout=5.0)
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _create_sample_mp4(path: Path, frames: int = 10, width: int = 64, height: int = 48) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, 10.0, (width, height))
    for i in range(frames):
        img = np.zeros((height, width, 3), dtype=np.uint8)
        img[:, :, i % 3] = 150
        writer.write(img)
    writer.release()
    return path


# ===========================================================================
# ISSUE 1 TESTS: Annotated Video Generation, Verification & Error Handling
# ===========================================================================

def test_annotated_video_generation_and_file_verification(fixture_setup, tmp_path):
    """Verify that a valid video generates a non-empty annotated MP4 file and persists in DB."""
    client = fixture_setup["client"]
    db = fixture_setup["db"]
    patient = fixture_setup["patient_a"]
    token = create_access_token(data={"sub": patient.id, "role": patient.role})
    client.headers["Authorization"] = f"Bearer {token}"

    sub = Subject(id="subj_v1", owner_id=patient.id, organization_id="org_med")
    db.add(sub)
    sess = DbSession(id="sess_v1", subject_id=sub.id)
    db.add(sess)
    db.commit()

    # Upload video
    video_file = _create_sample_mp4(tmp_path / "walk.mp4", frames=12)
    with open(video_file, "rb") as f:
        up = client.post(f"/api/v1/sessions/{sess.id}/recordings", files={"file": ("walk.mp4", f, "video/mp4")})
    assert up.status_code == 201
    rec_id = up.json()["id"]

    # Start analysis
    res_start = client.post(
        f"/api/v1/sessions/{sess.id}/analysis",
        json={"recording_id": rec_id, "camera_view": "side", "pose_model": "yolo"},
    )
    assert res_start.status_code == 202
    job_id = res_start.json()["id"]

    fixture_setup["jm"].wait_all(timeout=15.0)

    # Verify Job is completed
    job_res = client.get(f"/api/v1/jobs/{job_id}")
    assert job_res.status_code == 200
    assert job_res.json()["status"] == "completed"
    assert job_res.json()["recording_id"] == rec_id

    # Verify Recording DB state
    rec_res = client.get(f"/api/v1/recordings/{rec_id}")
    assert rec_res.status_code == 200
    rec_data = rec_res.json()
    assert rec_data["annotation_status"] == "completed"
    assert rec_data["annotated_video_path"] is not None

    ann_path = Path(rec_data["annotated_video_path"])
    assert ann_path.exists(), "Annotated video file must exist on disk"
    assert ann_path.stat().st_size > 0, "Annotated video file must have non-zero size"
    assert ann_path.suffix.lower() == ".mp4", "Annotated video must end with .mp4"

    # Verify Video Download / Stream
    vid_res = client.get(f"/api/v1/recordings/{rec_id}/annotated-video")
    assert vid_res.status_code == 200
    assert vid_res.headers["content-type"] == "video/mp4"
    assert len(vid_res.content) == ann_path.stat().st_size


def test_job_fails_when_annotation_fails_if_expected(fixture_setup, tmp_path):
    """When video recording is provided, annotation failure must fail the job instead of silently marking it completed."""
    client = fixture_setup["client"]
    db = fixture_setup["db"]
    patient = fixture_setup["patient_a"]
    token = create_access_token(data={"sub": patient.id, "role": patient.role})
    client.headers["Authorization"] = f"Bearer {token}"

    sub = Subject(id="subj_v2", owner_id=patient.id, organization_id="org_med")
    db.add(sub)
    sess = DbSession(id="sess_v2", subject_id=sub.id)
    db.add(sess)
    db.commit()

    video_file = _create_sample_mp4(tmp_path / "walk_fail.mp4", frames=8)
    with open(video_file, "rb") as f:
        up = client.post(f"/api/v1/sessions/{sess.id}/recordings", files={"file": ("walk_fail.mp4", f, "video/mp4")})
    assert up.status_code == 201
    rec_id = up.json()["id"]

    # Mock annotate_video to fail
    with patch("src.visualization.video_annotator.annotate_video", side_effect=VideoAnnotationError("Simulated encoder failure")):
        res_start = client.post(
            f"/api/v1/sessions/{sess.id}/analysis",
            json={"recording_id": rec_id, "camera_view": "side", "pose_model": "yolo"},
        )
        assert res_start.status_code == 202
        job_id = res_start.json()["id"]
        fixture_setup["jm"].wait_all(timeout=15.0)

    # Job MUST be marked failed, not completed
    job_res = client.get(f"/api/v1/jobs/{job_id}")
    assert job_res.status_code == 200
    job_data = job_res.json()
    assert job_data["status"] == "failed"
    assert "Annotated video generation failed" in job_data["error_message"]
    assert "Simulated encoder failure" in job_data["error_message"]

    # Recording annotation status must be failed
    rec_res = client.get(f"/api/v1/recordings/{rec_id}")
    assert rec_res.json()["annotation_status"] == "failed"


def test_retry_job_preserves_recording_and_reannotates(fixture_setup, tmp_path):
    """Verify that retrying a job preserves recording_id and recording_path."""
    client = fixture_setup["client"]
    db = fixture_setup["db"]
    patient = fixture_setup["patient_a"]
    token = create_access_token(data={"sub": patient.id, "role": patient.role})
    client.headers["Authorization"] = f"Bearer {token}"

    sub = Subject(id="subj_retry", owner_id=patient.id, organization_id="org_med")
    db.add(sub)
    sess = DbSession(id="sess_retry", subject_id=sub.id)
    db.add(sess)
    db.commit()

    video_file = _create_sample_mp4(tmp_path / "retry_walk.mp4", frames=6)
    with open(video_file, "rb") as f:
        up = client.post(f"/api/v1/sessions/{sess.id}/recordings", files={"file": ("retry_walk.mp4", f, "video/mp4")})
    rec_id = up.json()["id"]

    job = AnalysisJob(
        id="job_to_retry",
        session_id=sess.id,
        subject_id=sub.id,
        recording_id=rec_id,
        status="failed",
        error_message="Previous failure",
    )
    db.add(job)
    db.commit()

    # Retry the job
    res_retry = client.post(f"/api/v1/jobs/{job.id}/retry")
    assert res_retry.status_code == 200
    assert res_retry.json()["status"] == "queued"
    assert res_retry.json()["recording_id"] == rec_id

    fixture_setup["jm"].wait_all(timeout=15.0)

    # Poll final status
    final_res = client.get(f"/api/v1/jobs/{job.id}")
    assert final_res.json()["status"] == "completed"
    assert final_res.json()["recording_id"] == rec_id

    rec_res = client.get(f"/api/v1/recordings/{rec_id}")
    assert rec_res.json()["annotation_status"] == "completed"


# ===========================================================================
# ISSUE 2 TESTS: Report Generation, Storage, Formats & RBAC Downloads
# ===========================================================================

def test_report_generation_persistence_and_downloads(fixture_setup):
    """Verify generating both Individual and Professional reports, verifying disk storage,
    and downloading both in Markdown (.md) and HTML (.html) formats."""
    client = fixture_setup["client"]
    db = fixture_setup["db"]
    clinician = fixture_setup["clinician"]
    patient_a = fixture_setup["patient_a"]
    patient_b = fixture_setup["patient_b"]

    clinician_token = create_access_token(data={"sub": clinician.id, "role": clinician.role})
    patient_token = create_access_token(data={"sub": patient_a.id, "role": patient_a.role})

    # Setup subject & session
    sub = Subject(id="subj_reports", owner_id=patient_a.id, organization_id="org_med")
    db.add(sub)
    sess = DbSession(id="sess_reports", subject_id=sub.id)
    db.add(sess)
    db.commit()

    # 1. Generate Individual Report as Patient
    client.headers["Authorization"] = f"Bearer {patient_token}"
    ind_res = client.post(f"/api/v1/sessions/{sess.id}/reports", json={"report_type": "individual"})
    assert ind_res.status_code == 201
    ind_report_id = ind_res.json()["id"]

    # Verify Report Record in DB
    report_record = db.query(ReportRecord).filter(ReportRecord.id == ind_report_id).first()
    assert report_record is not None
    assert report_record.status == "generated"
    assert report_record.file_path is not None
    assert Path(report_record.file_path).exists()
    assert Path(report_record.file_path).stat().st_size > 0

    # 2. Download Individual Report as Markdown (.md)
    dl_md = client.get(f"/api/v1/reports/{ind_report_id}/download?format=md")
    assert dl_md.status_code == 200
    assert "text/markdown" in dl_md.headers["content-type"]
    assert "attachment" in dl_md.headers["content-disposition"]
    assert dl_md.headers["content-disposition"].endswith('.md"')
    assert "Gait Analysis Summary" in dl_md.text
    assert len(dl_md.content) > 50

    # 3. Download Individual Report as HTML (.html)
    dl_html = client.get(f"/api/v1/reports/{ind_report_id}/download?format=html")
    assert dl_html.status_code == 200
    assert "text/html" in dl_html.headers["content-type"]
    assert "attachment" in dl_html.headers["content-disposition"]
    assert dl_html.headers["content-disposition"].endswith('.html"')
    assert "<!DOCTYPE html>" in dl_html.text
    assert "<h1>Gait Analysis Summary</h1>" in dl_html.text
    assert len(dl_html.content) > 100

    # 4. Patient attempts to generate Professional Report -> 403 Forbidden
    pro_denied = client.post(f"/api/v1/sessions/{sess.id}/reports", json={"report_type": "professional"})
    assert pro_denied.status_code == 403

    # 5. Clinician generates Professional Report -> 201 Created
    client.headers["Authorization"] = f"Bearer {clinician_token}"
    pro_res = client.post(f"/api/v1/sessions/{sess.id}/reports", json={"report_type": "professional"})
    assert pro_res.status_code == 201
    pro_report_id = pro_res.json()["id"]

    # 6. Clinician downloads Professional Report (.md and .html)
    dl_pro_md = client.get(f"/api/v1/reports/{pro_report_id}/download?format=md")
    assert dl_pro_md.status_code == 200
    assert "Professional" in dl_pro_md.text

    dl_pro_html = client.get(f"/api/v1/reports/{pro_report_id}/download?format=html")
    assert dl_pro_html.status_code == 200
    assert "<!DOCTYPE html>" in dl_pro_html.text
    assert "<table>" in dl_pro_html.text

    # 7. Patient attempts to download Professional Report -> 403 Forbidden
    client.headers["Authorization"] = f"Bearer {patient_token}"
    denied_dl = client.get(f"/api/v1/reports/{pro_report_id}/download?format=md")
    assert denied_dl.status_code == 403

    # 8. Patient B (another user) attempts to access Patient A's report -> 403 Forbidden
    token_b = create_access_token(data={"sub": patient_b.id, "role": patient_b.role})
    client.headers["Authorization"] = f"Bearer {token_b}"
    b_denied = client.get(f"/api/v1/reports/{ind_report_id}/download")
    assert b_denied.status_code == 403

    # 9. Unauthenticated request -> 401 Unauthorized (never downloads empty or html error page)
    client.headers.pop("Authorization", None)
    unauth_dl = client.get(f"/api/v1/reports/{ind_report_id}/download")
    assert unauth_dl.status_code == 401
