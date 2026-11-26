"""Tests for longitudinal progress comparison, reliability rules, and clinical/patient report workflows."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.auth.security import create_access_token, hash_password
from src.api.dependencies import get_db, get_job_manager
from src.api.main import app
from src.database.database import Base, init_db
from src.database.models import AssessmentRecord, Recording, ReportRecord, Session as DbSession, Subject, User
from src.jobs.job_manager import JobManager


@pytest.fixture
def setup_env():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    clinician = User(
        id=str(uuid.uuid4()),
        username="dr_rehab",
        hashed_password=hash_password("pw"),
        role="professional",
        organization_id="org_rehab",
    )
    patient = User(
        id=str(uuid.uuid4()),
        username="patient_rehab",
        hashed_password=hash_password("pw"),
        role="individual",
        organization_id="org_rehab",
    )
    other_patient = User(
        id=str(uuid.uuid4()),
        username="patient_other",
        hashed_password=hash_password("pw"),
        role="individual",
        organization_id="org_rehab",
    )
    db.add_all([clinician, patient, other_patient])
    db.commit()

    jm = JobManager(db_session_factory=SessionLocal, max_workers=2)

    def _override_db():
        s = SessionLocal()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_job_manager] = lambda: jm
    client = TestClient(app)

    yield {
        "db": db,
        "jm": jm,
        "client": client,
        "clinician": clinician,
        "patient": patient,
        "other_patient": other_patient,
    }

    jm.wait_all(timeout=5.0)
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _seed_session_with_assessment(
    db,
    subject_id: str,
    days_ago: int,
    walking_speed: float | None,
    cadence: float | None,
    cadence_conf: float = 0.85,
    cadence_status: str = "supported",
    approval_status: str = "pending_review",
    validation_status: str = "passed",
) -> str:
    sess_id = str(uuid.uuid4())
    created = datetime.utcnow() - timedelta(days=days_ago)
    sess = DbSession(
        id=sess_id,
        subject_id=subject_id,
        walking_speed_ms=walking_speed,
        camera_view="side",
        calibration_status="calibrated" if walking_speed else "uncalibrated",
        created_at=created,
    )
    db.add(sess)
    rec = Recording(
        id=str(uuid.uuid4()),
        session_id=sess_id,
        server_filename="walk.mp4",
        file_path="data/uploads/walk.mp4",
        validation_status=validation_status,
        created_at=created,
    )
    db.add(rec)

    interps = []
    if cadence is not None:
        interps.append({
            "feature_name": "cadence_steps_per_min",
            "category": "temporal",
            "value": cadence,
            "unit": "steps/min",
            "status": cadence_status,
            "confidence": cadence_conf,
            "interpretation_text": "Measured cadence.",
            "evidence_sources": ["pose"],
            "limitations": [],
        })
    if walking_speed is not None and walking_speed > 0:
        interps.append({
            "feature_name": "walking_speed_ms",
            "category": "spatial",
            "value": walking_speed,
            "unit": "m/s",
            "status": "supported",
            "confidence": 0.85,
            "interpretation_text": "Measured walking speed.",
            "evidence_sources": ["calibrated"],
            "limitations": [],
        })

    ass = AssessmentRecord(
        id=str(uuid.uuid4()),
        subject_id=subject_id,
        session_id=sess_id,
        recording_id=rec.id,
        assessment_data={"feature_interpretations": interps, "global_limitations": ["2D planar estimate"]},
        overall_status="supported" if cadence_status == "supported" else "limited_evidence",
        approval_status=approval_status,
        created_at=created,
    )
    db.add(ass)
    db.commit()
    return sess_id


def test_longitudinal_progress_chronological_deltas_and_reliability_exclusion(setup_env):
    db = setup_env["db"]
    client = setup_env["client"]
    clinician = setup_env["clinician"]
    patient = setup_env["patient"]

    sub = Subject(id="sub_long_1", owner_id=patient.id, organization_id="org_rehab", display_name="Rehab Patient")
    db.add(sub)
    db.commit()

    # Empty history returns clean empty response
    tok_c = create_access_token(data={"sub": clinician.id, "role": clinician.role})
    client.headers["Authorization"] = f"Bearer {tok_c}"
    empty_res = client.get(f"/api/v1/subjects/{sub.id}/longitudinal")
    assert empty_res.status_code == 200
    assert empty_res.json()["total_sessions"] == 0
    assert empty_res.json()["walking_speed"]["trend"] == "insufficient_data"

    # Seed chronological sessions:
    # 1. Baseline (30 days ago): ws=0.45 m/s, cad=82.0 steps/min (valid)
    _seed_session_with_assessment(db, sub.id, days_ago=30, walking_speed=0.45, cadence=82.0)
    # 2. Low-confidence session (20 days ago): ws=None, cad=145.0 with conf=0.35 (MUST be excluded from baseline/latest)
    _seed_session_with_assessment(db, sub.id, days_ago=20, walking_speed=None, cadence=145.0, cadence_conf=0.35, cadence_status="limited_evidence")
    # 3. Failed validation session (15 days ago): MUST be excluded
    _seed_session_with_assessment(db, sub.id, days_ago=15, walking_speed=0.20, cadence=60.0, validation_status="failed")
    # 4. Latest formal approved assessment (2 days ago): ws=0.62 m/s, cad=98.0 steps/min (valid)
    _seed_session_with_assessment(db, sub.id, days_ago=2, walking_speed=0.62, cadence=98.0, approval_status="approved")

    res = client.get(f"/api/v1/subjects/{sub.id}/longitudinal")
    assert res.status_code == 200
    data = res.json()

    assert data["total_sessions"] == 4
    assert data["valid_sessions_count"] == 2
    assert data["unavailable_or_unreliable_count"] == 2

    # Chronological order oldest -> newest
    dates = [t["date"] for t in data["timeline"]]
    assert dates == sorted(dates)
    assert data["timeline"][-1]["record_type"] == "clinical_assessment"

    # Walking speed calculations: 0.45 -> 0.62 = +0.17 (+37.78%)
    ws = data["walking_speed"]
    assert ws["baseline_value"] == 0.45
    assert ws["latest_value"] == 0.62
    assert ws["absolute_change"] == pytest.approx(0.17, abs=1e-3)
    assert ws["percentage_change"] == pytest.approx(37.78, abs=0.1)
    assert ws["trend"] == "improved"

    # Cadence calculations: 82.0 -> 98.0 (into 90-130 target band) = +16.0 (+19.51%)
    cad = data["cadence"]
    assert cad["baseline_value"] == 82.0
    assert cad["latest_value"] == 98.0
    assert cad["absolute_change"] == pytest.approx(16.0, abs=1e-2)
    assert cad["trend"] == "improved"


def test_cadence_abnormal_increase_not_falsely_marked_improved(setup_env):
    db = setup_env["db"]
    client = setup_env["client"]
    clinician = setup_env["clinician"]
    patient = setup_env["patient"]

    sub = Subject(id="sub_cad_rule", owner_id=patient.id, organization_id="org_rehab")
    db.add(sub)
    db.commit()

    _seed_session_with_assessment(db, sub.id, days_ago=10, walking_speed=0.80, cadence=125.0)
    _seed_session_with_assessment(db, sub.id, days_ago=1, walking_speed=0.80, cadence=145.0)

    tok_c = create_access_token(data={"sub": clinician.id, "role": clinician.role})
    res = client.get(f"/api/v1/subjects/{sub.id}/longitudinal", headers={"Authorization": f"Bearer {tok_c}"})
    assert res.status_code == 200
    assert res.json()["cadence"]["trend"] == "declined"


def test_complete_rehab_e2e_video_progress_clinical_and_patient_report_workflow(setup_env, tmp_path):
    db = setup_env["db"]
    client = setup_env["client"]
    clinician = setup_env["clinician"]
    patient = setup_env["patient"]
    other_patient = setup_env["other_patient"]

    tok_c = create_access_token(data={"sub": clinician.id, "role": clinician.role})
    tok_p = create_access_token(data={"sub": patient.id, "role": patient.role})
    tok_other = create_access_token(data={"sub": other_patient.id, "role": other_patient.role})

    # 1. Create subject & baseline session with measured speed
    client.headers["Authorization"] = f"Bearer {tok_c}"
    sub_id = client.post("/api/v1/subjects", json={"display_name": "E2E Rehab"}).json()["id"]
    # Assign owner to patient
    sub_obj = db.query(Subject).filter(Subject.id == sub_id).first()
    sub_obj.owner_id = patient.id
    db.commit()

    _seed_session_with_assessment(db, sub_id, days_ago=14, walking_speed=0.50, cadence=85.0)

    # 2. Create new session, upload walking video, run analysis
    s2 = client.post(
        f"/api/v1/subjects/{sub_id}/sessions",
        json={"camera_view": "side", "walking_speed_ms": 0.68, "calibration_status": "calibrated"},
    ).json()
    s2_id = s2["id"]

    vid = tmp_path / "e2e_walk.mp4"
    w = cv2.VideoWriter(str(vid), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (64, 48))
    for _ in range(6):
        w.write(np.zeros((48, 64, 3), dtype=np.uint8))
    w.release()

    with open(vid, "rb") as f:
        rec = client.post(f"/api/v1/sessions/{s2_id}/recordings", files={"file": ("e2e_walk.mp4", f, "video/mp4")}).json()

    job = client.post(
        f"/api/v1/sessions/{s2_id}/analysis",
        json={"recording_id": rec["id"], "camera_view": "side", "pose_model": "synthetic"},
    ).json()
    setup_env["jm"].wait_all(timeout=15.0)
    assert client.get(f"/api/v1/jobs/{job['id']}").json()["status"] == "completed"

    # 3. Retrieve longitudinal progress -> shows 2 sessions
    prog = client.get(f"/api/v1/subjects/{sub_id}/longitudinal").json()
    assert prog["total_sessions"] == 2
    assert prog["walking_speed"]["baseline_value"] == 0.5
    assert prog["walking_speed"]["latest_value"] == 0.68
    assert prog["walking_speed"]["trend"] == "improved"

    # 4. Clinician generates Clinical Report + Patient Report (both start as draft)
    pro_rep = client.post(f"/api/v1/sessions/{s2_id}/reports", json={"report_type": "professional"}).json()
    pat_rep = client.post(f"/api/v1/sessions/{s2_id}/reports", json={"report_type": "individual"}).json()
    assert pro_rep["status"] == "draft"
    assert pat_rep["status"] == "draft"
    assert "clinical_interpretation" in pro_rep["report_data"]
    assert "achievements" in pat_rep["report_data"]

    # 5. Patient CANNOT view draft report or professional report or edit/approve
    client.headers["Authorization"] = f"Bearer {tok_p}"
    assert client.get(f"/api/v1/reports/{pat_rep['id']}").status_code == 403
    assert client.get(f"/api/v1/reports/{pro_rep['id']}").status_code == 403
    assert client.post(f"/api/v1/reports/{pat_rep['id']}/approve").status_code == 403
    assert client.get("/api/v1/reports").json() == []

    # 6. Clinician adds notes/recommendations, approves, and publishes patient report
    client.headers["Authorization"] = f"Bearer {tok_c}"
    upd = client.patch(
        f"/api/v1/reports/{pat_rep['id']}",
        json={
            "clinician_notes": "Good stride consistency.",
            "rehabilitation_priorities": ["Continue daily 15-minute walks"],
            "recommendations": "Follow up in 2 weeks.",
        },
    )
    assert upd.status_code == 200
    assert client.post(f"/api/v1/reports/{pat_rep['id']}/approve").json()["status"] == "approved"
    pub = client.post(f"/api/v1/reports/{pat_rep['id']}/publish").json()
    assert pub["status"] == "published"
    assert len(pub["revision_history"]) >= 3

    # 7. Patient views published report and clinician-approved next steps
    client.headers["Authorization"] = f"Bearer {tok_p}"
    vis_list = client.get("/api/v1/reports").json()
    assert len(vis_list) == 1
    assert vis_list[0]["id"] == pat_rep["id"]
    pat_view = client.get(f"/api/v1/reports/{pat_rep['id']}").json()
    assert "Continue daily 15-minute walks" in pat_view["report_data"]["clinician_approved_next_steps"]

    # 8. Other patient cannot view published report (403)
    client.headers["Authorization"] = f"Bearer {tok_other}"
    assert client.get(f"/api/v1/reports/{pat_rep['id']}").status_code == 403


def test_database_migration_preserves_legacy_records_and_is_idempotent(tmp_path):
    db_file = tmp_path / "legacy_rehab.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT, email TEXT, hashed_password TEXT, role TEXT, is_active BOOLEAN, created_at DATETIME, updated_at DATETIME)")
    conn.execute("CREATE TABLE subjects (id TEXT PRIMARY KEY, display_name TEXT, owner_id TEXT, is_deleted BOOLEAN, created_at DATETIME, updated_at DATETIME)")
    conn.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, subject_id TEXT, walking_speed_ms REAL, camera_view TEXT, calibration_status TEXT, is_deleted BOOLEAN, created_at DATETIME, updated_at DATETIME)")
    conn.execute("CREATE TABLE recordings (id TEXT PRIMARY KEY, session_id TEXT, server_filename TEXT, file_path TEXT, validation_status TEXT, is_deleted BOOLEAN, created_at DATETIME)")
    conn.execute("CREATE TABLE assessments (id TEXT PRIMARY KEY, subject_id TEXT, session_id TEXT, assessment_data TEXT, overall_status TEXT, created_at DATETIME)")
    conn.execute("CREATE TABLE reports (id TEXT PRIMARY KEY, subject_id TEXT, session_id TEXT, report_type TEXT, status TEXT, is_deleted BOOLEAN, generated_at DATETIME)")
    conn.execute("INSERT INTO subjects (id, display_name, is_deleted) VALUES ('legacy_s1', 'Legacy Patient', 0)")
    conn.commit()
    conn.close()

    db_url = f"sqlite:///{db_file}"
    init_db(db_url)
    init_db(db_url)  # Second run must be idempotent

    conn = sqlite3.connect(str(db_file))
    row = conn.execute("SELECT id, display_name FROM subjects WHERE id = 'legacy_s1'").fetchone()
    assert row == ("legacy_s1", "Legacy Patient")
    rep_cols = [r[1] for r in conn.execute("PRAGMA table_info(reports)").fetchall()]
    assert "clinician_notes" in rep_cols
    assert "published_at" in rep_cols
    conn.close()
