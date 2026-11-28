"""Feature 02 integration: gait-cycle results are stored, linked to the session/recording and served by the API."""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.auth.security import create_access_token, hash_password
from src.api.dependencies import get_db
from src.api.main import app
from src.database import models
from src.database.database import Base
from src.gait_events.gait_cycle_analysis import analyze_gait_cycles
from src.jobs.task_registry import run_analysis_pipeline
from tests.test_gait_cycle_analysis import FPS, make_walker


@pytest.fixture
def env(tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    tokens = {}
    with SessionLocal() as db:
        for name, role in (("gc_clin", "professional"), ("gc_pat", "individual"), ("gc_other", "individual")):
            u = models.User(id=str(uuid.uuid4()), username=name, hashed_password=hash_password("x"), role=role,
                            organization_id="default_org")
            db.add(u)
            db.commit()
            tokens[name] = create_access_token(data={"sub": u.id, "role": role})
            if name == "gc_pat":
                patient_id = u.id
        subj = models.Subject(display_name="GC", owner_id=patient_id, organization_id="default_org")
        db.add(subj)
        db.commit()
        sess = models.Session(subject_id=subj.id, camera_view="side")
        db.add(sess)
        db.commit()
        video = tmp_path / "walk.mp4"
        video.write_bytes(b"0")
        rec = models.Recording(session_id=sess.id, server_filename="walk.mp4", file_path=str(video), camera_view="side")
        db.add(rec)
        db.commit()
        ids = SimpleIds(subj.id, sess.id, rec.id, str(video))

    def override():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    client = TestClient(app)

    def as_user(name):
        client.headers["Authorization"] = f"Bearer {tokens[name]}"
        return client

    yield SessionLocal, ids, as_user
    app.dependency_overrides.clear()
    engine.dispose()


class SimpleIds:
    def __init__(self, subject_id, session_id, recording_id, path):
        self.subject_id, self.session_id, self.recording_id, self.path = subject_id, session_id, recording_id, path


def _run(SessionLocal, ids, analysis):
    val = MagicMock(is_valid=True, issues=[])
    val.metadata.fps, val.metadata.duration_seconds, val.metadata.width, val.metadata.height = 30.0, 6.0, 1280, 720
    res = MagicMock()
    res.poses, res.gait_cycles, res.measurements = [], [], []
    res.camera_view.predicted_view = "side"
    res.gait_cycle_analysis = analysis

    def fake_annotate(db, recording_path, recording_id, partial_results, poses):
        partial_results["annotation_status"] = "completed"

    with SessionLocal() as db:
        job = models.AnalysisJob(session_id=ids.session_id, subject_id=ids.subject_id, recording_id=ids.recording_id)
        db.add(job)
        db.commit()
        with patch("src.video.video_validator.validate_video", return_value=val), \
             patch("src.video.video_pipeline_runner.process_video_pipeline", return_value=res), \
             patch("src.jobs.task_registry._annotate_recording", side_effect=fake_annotate):
            run_analysis_pipeline(job_id=job.id, db=db, recording_path=ids.path, session_id=ids.session_id,
                                  subject_id=ids.subject_id, recording_id=ids.recording_id)
        return job.id


def test_results_stored_and_linked_to_session(env):
    SessionLocal, ids, as_user = env
    analysis = analyze_gait_cycles(make_walker(), "side", FPS)
    job_id = _run(SessionLocal, ids, analysis)

    with SessionLocal() as db:
        rows = db.query(models.GaitCycleAnalysisRecord).all()
        assert len(rows) == 1
        row = rows[0]
        assert (row.session_id, row.recording_id, row.job_id) == (ids.session_id, ids.recording_id, job_id)
        assert row.status == "analysed" and row.method_version == "gait_cycle_v1"
        assert row.analysis_data["counts"]["cycles_valid"] >= 6
        job = db.get(models.AnalysisJob, job_id)
        assert job.status == "completed"
        assert job.result_data["gait_cycle"]["status"] == "analysed"

    # Re-analysis updates the same record instead of duplicating it.
    _run(SessionLocal, ids, analysis)
    with SessionLocal() as db:
        assert db.query(models.GaitCycleAnalysisRecord).count() == 1


def test_api_individual_and_aggregate_review(env):
    SessionLocal, ids, as_user = env
    _run(SessionLocal, ids, analyze_gait_cycles(make_walker(), "side", FPS))
    c = as_user("gc_clin")

    r = c.get(f"/api/v1/recordings/{ids.recording_id}/gait-cycles")
    assert r.status_code == 200
    a = r.json()["analysis"]
    assert r.json()["session_id"] == ids.session_id
    assert a["events"] and all("timestamp_s" in e and "confidence" in e for e in a["events"])
    assert any(c_["included_in_aggregate"] for c_ in a["cycles"])  # individual cycles
    assert any(m["name"] == "stance_pct" and m["side"] == "left" for m in a["phase_metrics"])  # aggregates
    assert a["subphase_summary"]["left"]
    assert all(m["measurement_type"] == "estimated" for m in a["phase_metrics"])

    s = c.get(f"/api/v1/sessions/{ids.session_id}/gait-cycles")
    assert s.status_code == 200 and len(s.json()) == 1
    assert s.json()[0]["recording_id"] == ids.recording_id
    assert "analysis" not in s.json()[0] and s.json()[0]["summary"]["counts"]["cycles_valid"] >= 6


def test_api_access_control_and_missing(env):
    SessionLocal, ids, as_user = env
    assert as_user("gc_clin").get(f"/api/v1/recordings/{ids.recording_id}/gait-cycles").status_code == 404
    _run(SessionLocal, ids, analyze_gait_cycles(make_walker(), "side", FPS))
    assert as_user("gc_other").get(f"/api/v1/recordings/{ids.recording_id}/gait-cycles").status_code == 403
    assert as_user("gc_other").get(f"/api/v1/sessions/{ids.session_id}/gait-cycles").status_code == 403
    assert as_user("gc_pat").get(f"/api/v1/recordings/{ids.recording_id}/gait-cycles").status_code == 200
    assert as_user("gc_clin").get("/api/v1/recordings/nope/gait-cycles").status_code == 404


def test_unsupported_view_stored_with_reason(env):
    SessionLocal, ids, as_user = env
    with SessionLocal() as db:  # recording labelled as a front view
        db.get(models.Recording, ids.recording_id).camera_view = "front"
        db.commit()
    _run(SessionLocal, ids, analyze_gait_cycles(make_walker(), "front", FPS))
    body = as_user("gc_clin").get(f"/api/v1/recordings/{ids.recording_id}/gait-cycles").json()
    assert body["status"] == "not_supported_view"
    assert body["analysis"]["warnings"]


def _run_with_poses(SessionLocal, ids, analysis, poses, **kwargs):
    """Like _run, but the mocked pipeline also returns poses (needed for view re-analysis)."""
    val = MagicMock(is_valid=True, issues=[])
    val.metadata.fps, val.metadata.duration_seconds, val.metadata.width, val.metadata.height = 30.0, 6.0, 1280, 720
    res = MagicMock()
    res.poses, res.gait_cycles = poses, []
    res.measurements = [MagicMock(feature_name="cadence", value=90.0, confidence=0.8, cycle_consistency_sd=None)]
    res.camera_view.predicted_view = analysis.camera_view
    res.gait_cycle_analysis = analysis

    def fake_annotate(db, recording_path, recording_id, partial_results, poses):
        partial_results["annotation_status"] = "completed"

    with SessionLocal() as db:
        job = models.AnalysisJob(session_id=ids.session_id, subject_id=ids.subject_id, recording_id=ids.recording_id)
        db.add(job)
        db.commit()
        with patch("src.video.video_validator.validate_video", return_value=val), \
             patch("src.video.video_pipeline_runner.process_video_pipeline", return_value=res), \
             patch("src.jobs.task_registry._annotate_recording", side_effect=fake_annotate):
            run_analysis_pipeline(job_id=job.id, db=db, recording_path=ids.path, session_id=ids.session_id,
                                  subject_id=ids.subject_id, recording_id=ids.recording_id, **kwargs)
        return job.id


def test_recording_label_overrides_detected_view(env):
    SessionLocal, ids, as_user = env
    poses = make_walker()
    # Detector says "front"; the recording (fixture) is labelled "side".
    _run_with_poses(SessionLocal, ids, analyze_gait_cycles(poses, "front", FPS), poses)
    body = as_user("gc_clin").get(f"/api/v1/recordings/{ids.recording_id}/gait-cycles").json()
    assert body["status"] == "analysed" and body["camera_view"] == "side"
    assert body["analysis"]["view_source"] == "labelled" and body["analysis"]["detected_view"] == "front"


def test_assessment_uses_step_based_cadence(env):
    SessionLocal, ids, as_user = env
    poses = make_walker()
    job_id = _run_with_poses(SessionLocal, ids, analyze_gait_cycles(poses, "side", FPS), poses)
    with SessionLocal() as db:
        job = db.get(models.AnalysisJob, job_id)
        assert job.result_data["cadence_source"] == "gait_cycle_step_based"
        cad = job.result_data["features"]["cadence_steps_per_min"]
        assert cad == pytest.approx(120.0 / 1.1, abs=3.0)  # not the legacy 90.0
        assert job.result_data["features"]["cadence"] == cad


def test_assessment_keeps_legacy_cadence_when_unsupported(env):
    SessionLocal, ids, as_user = env
    poses = make_walker(conf=0.4)  # all events low confidence
    job_id = _run_with_poses(SessionLocal, ids, analyze_gait_cycles(poses, "side", FPS), poses)
    with SessionLocal() as db:
        job = db.get(models.AnalysisJob, job_id)
        assert job.result_data["cadence_source"] == "legacy_cycle_frequency"
        assert job.result_data["features"]["cadence"] == 90.0


def test_gait_cycle_metrics_in_multiview_combined(env):
    SessionLocal, ids, as_user = env
    poses = make_walker(stance_frac=(0.63, 0.57))
    _run_with_poses(SessionLocal, ids, analyze_gait_cycles(poses, "side", FPS), poses)
    mv = as_user("gc_clin").get(f"/api/v1/sessions/{ids.session_id}/multiview").json()
    side = next(v for v in mv["views"] if v["camera_view"] == "side")
    assert side["gait_cycle_status"] == "analysed"
    combined = {m["feature_name"]: m for m in mv["combined"]["measurements"]}
    for name, expected in (("left_stance_pct", 63.0), ("right_stance_pct", 57.0)):
        m = combined[name]
        assert m["status"] == "combined" and m["source_view"] == "side"
        assert m["value"] == pytest.approx(expected, abs=3.0)
    assert combined["double_support_pct"]["eligible_views"] == ["side"]
