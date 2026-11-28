"""Tests for Feature 01: Multi-view Gait Assessment."""
import json
import sqlite3
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.api.dependencies import get_db, get_job_manager, get_storage
from src.api.main import app
from src.assessment.multiview_summary import (
    build_multiview_summary,
    combine_measurements,
    eligible_views_for_metric,
)
from src.database import models
from src.database.database import Base
from src.jobs.job_manager import JobManager
from src.storage.file_storage import FileStorage


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture
def env():
    """API client with an isolated in-memory DB, a clinician, a patient and another patient."""
    from src.api.auth.security import create_access_token, hash_password

    with tempfile.TemporaryDirectory() as tmpdir:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        storage = FileStorage(storage_root=Path(tmpdir) / "uploads")
        jm = JobManager(db_session_factory=SessionLocal, max_workers=1)

        tokens = {}
        with SessionLocal() as db:
            for name, role in (("mv_clin", "professional"), ("mv_pat", "individual"), ("mv_other", "individual")):
                u = models.User(id=str(uuid.uuid4()), username=name, hashed_password=hash_password("Pass@123"),
                                role=role, organization_id="default_org", is_active=True)
                db.add(u)
                db.commit()
                tokens[name] = (u.id, create_access_token(data={"sub": u.id, "role": u.role}))
            subj = models.Subject(id=str(uuid.uuid4()), display_name="MV Patient", owner_id=tokens["mv_pat"][0],
                                  organization_id="default_org")
            db.add(subj)
            db.commit()
            subject_id = subj.id

        def override_db():
            db = SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        app.dependency_overrides[get_storage] = lambda: storage
        app.dependency_overrides[get_job_manager] = lambda: jm

        with TestClient(app) as c:
            def as_user(name):
                c.headers["Authorization"] = f"Bearer {tokens[name][1]}"
                return c
            as_user("mv_pat")
            yield SimpleNamespace(client=c, as_user=as_user, subject_id=subject_id, SessionLocal=SessionLocal)

        jm.wait_all(timeout=5.0)
        app.dependency_overrides.clear()
        engine.dispose()


def _upload(c, session_id, view=None, name="walk.mp4", **extra):
    data = {}
    if view:
        data["camera_view"] = view
    data.update(extra)
    return c.post(
        f"/api/v1/sessions/{session_id}/recordings",
        files={"file": (name, b"0" * 2048, "video/mp4")},
        data=data,
    )


def _new_mv_session(env, views=("front", "side", "rear"), key=None):
    body = {"selected_views": list(views)}
    if key:
        body["client_request_id"] = key
    return env.client.post(f"/api/v1/subjects/{env.subject_id}/sessions", json=body)


# --------------------------------------------------------------------------- #
# Session management                                                          #
# --------------------------------------------------------------------------- #

def test_create_multiview_session_sets_mode_and_primary_view(env):
    r = _new_mv_session(env, views=["rear", "front"])
    assert r.status_code == 201
    s = r.json()
    assert s["assessment_mode"] == "multi_view"
    assert s["selected_views"] == ["front", "rear"]  # stable clinical ordering
    assert s["camera_view"] == "front"
    assert s["id"]


def test_invalid_view_rejected(env):
    r = env.client.post(f"/api/v1/subjects/{env.subject_id}/sessions", json={"selected_views": ["top"]})
    assert r.status_code == 422
    r = env.client.post(f"/api/v1/subjects/{env.subject_id}/sessions", json={"selected_views": []})
    assert r.status_code == 422


def test_idempotent_session_creation_prevents_duplicates(env):
    key = str(uuid.uuid4())
    r1 = _new_mv_session(env, key=key)
    r2 = _new_mv_session(env, key=key)
    assert r1.status_code == 201
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    listed = env.client.get(f"/api/v1/subjects/{env.subject_id}/sessions").json()
    assert listed["total"] == 1
    # A different key creates a new, distinct session.
    r3 = _new_mv_session(env, key=str(uuid.uuid4()))
    assert r3.json()["id"] != r1.json()["id"]


def test_recording_all_views_does_not_create_new_sessions(env):
    sid = _new_mv_session(env).json()["id"]
    for v in ("front", "side", "rear"):
        assert _upload(env.client, sid, v).status_code == 201
    listed = env.client.get(f"/api/v1/subjects/{env.subject_id}/sessions").json()
    assert listed["total"] == 1


def test_update_selected_views(env):
    sid = _new_mv_session(env, views=["side"]).json()["id"]
    r = env.client.patch(f"/api/v1/sessions/{sid}/views", json={"selected_views": ["side", "front"]})
    assert r.status_code == 200
    assert r.json()["selected_views"] == ["front", "side"]
    assert env.client.patch(f"/api/v1/sessions/{sid}/views", json={"selected_views": ["diag"]}).status_code == 422


# --------------------------------------------------------------------------- #
# Recording management                                                        #
# --------------------------------------------------------------------------- #

def test_multiple_recordings_share_session_id_with_metadata(env):
    sid = _new_mv_session(env).json()["id"]
    meta = {"client_duration_seconds": 8.2, "mime_type": "video/webm", "mean_luminance": 120}
    ids = {}
    for v in ("front", "side", "rear"):
        r = _upload(env.client, sid, v, recording_source="webcam",
                    recorded_at="2026-11-28T10:00:00Z", recording_metadata=json.dumps(meta))
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["session_id"] == sid
        assert body["camera_view"] == v
        assert body["recording_source"] == "webcam"
        assert body["recorded_at"].startswith("2026-11-28T10:00:00")
        assert body["recording_metadata"]["client_duration_seconds"] == 8.2
        assert body["is_superseded"] is False
        ids[v] = body["id"]

    recs = env.client.get(f"/api/v1/sessions/{sid}/recordings").json()
    assert {r["id"] for r in recs} == set(ids.values())
    assert all(r["session_id"] == sid for r in recs)


@pytest.mark.parametrize("field,value", [
    ("camera_view", "diagonal"),
    ("recording_source", "drone"),
    ("recorded_at", "yesterday"),
    ("recording_metadata", "[1,2]"),
    ("recording_metadata", "not json"),
])
def test_invalid_recording_metadata_rejected(env, field, value):
    sid = _new_mv_session(env).json()["id"]
    r = env.client.post(f"/api/v1/sessions/{sid}/recordings",
                        files={"file": ("w.mp4", b"0" * 100, "video/mp4")}, data={field: value})
    assert r.status_code == 400
    assert env.client.get(f"/api/v1/sessions/{sid}/recordings").json() == []


def test_retake_supersedes_only_same_view(env):
    sid = _new_mv_session(env).json()["id"]
    first_front = _upload(env.client, sid, "front").json()
    side = _upload(env.client, sid, "side").json()
    retake = _upload(env.client, sid, "front").json()

    all_recs = {r["id"]: r for r in env.client.get(f"/api/v1/sessions/{sid}/recordings").json()}
    assert all_recs[first_front["id"]]["is_superseded"] is True
    assert all_recs[first_front["id"]]["superseded_by_id"] == retake["id"]
    assert all_recs[side["id"]]["is_superseded"] is False
    assert all_recs[retake["id"]]["is_superseded"] is False
    # Original take is preserved (not deleted) for auditability.
    assert len(all_recs) == 3

    active = env.client.get(f"/api/v1/sessions/{sid}/recordings", params={"include_superseded": False}).json()
    assert {r["id"] for r in active} == {side["id"], retake["id"]}

    mv = env.client.get(f"/api/v1/sessions/{sid}/multiview").json()
    front = next(v for v in mv["views"] if v["camera_view"] == "front")
    assert front["recording"]["id"] == retake["id"]
    assert front["retake_count"] == 1


def test_analysis_rejects_recording_from_other_session(env):
    s1 = _new_mv_session(env).json()["id"]
    s2 = _new_mv_session(env).json()["id"]
    rec = _upload(env.client, s1, "side").json()
    r = env.client.post(f"/api/v1/sessions/{s2}/analysis", json={"recording_id": rec["id"]})
    assert r.status_code == 400


# --------------------------------------------------------------------------- #
# Consolidated assessment                                                     #
# --------------------------------------------------------------------------- #

def test_missing_views_reported(env):
    sid = _new_mv_session(env).json()["id"]
    mv = env.client.get(f"/api/v1/sessions/{sid}/multiview").json()
    assert mv["recording_status"] == "not_started"
    assert mv["missing_views"] == ["front", "side", "rear"]
    assert mv["combined"]["status"] == "not_available"
    assert mv["combined"]["is_3d_reconstruction"] is False

    _upload(env.client, sid, "side")
    mv = env.client.get(f"/api/v1/sessions/{sid}/multiview").json()
    assert mv["recording_status"] == "incomplete"
    assert mv["missing_views"] == ["front", "rear"]
    statuses = {v["camera_view"]: v["status"] for v in mv["views"]}
    assert statuses == {"front": "missing", "side": "recorded", "rear": "missing"}
    assert any("Missing views" in lim for lim in mv["combined"]["limitations"])

    _upload(env.client, sid, "front")
    _upload(env.client, sid, "rear")
    mv = env.client.get(f"/api/v1/sessions/{sid}/multiview").json()
    assert mv["recording_status"] == "complete"
    assert mv["missing_views"] == []


def test_multiview_session_persists_and_resumes(env):
    sid = _new_mv_session(env, views=["front", "side"]).json()["id"]
    _upload(env.client, sid, "front")
    # "Resume later": a fresh request sees the same session state.
    s = env.client.get(f"/api/v1/sessions/{sid}").json()
    assert s["selected_views"] == ["front", "side"]
    mv = env.client.get(f"/api/v1/sessions/{sid}/multiview").json()
    assert mv["subject_display_name"] == "MV Patient"
    assert mv["session_created_at"]
    assert mv["missing_views"] == ["side"]


def test_multiview_access_control(env):
    sid = _new_mv_session(env).json()["id"]
    env.as_user("mv_other")
    assert env.client.get(f"/api/v1/sessions/{sid}/multiview").status_code == 403
    assert _upload(env.client, sid, "front").status_code == 403
    assert env.client.patch(f"/api/v1/sessions/{sid}/views", json={"selected_views": ["side"]}).status_code == 403
    env.as_user("mv_clin")
    assert env.client.get(f"/api/v1/sessions/{sid}/multiview").status_code == 200


def test_assessment_and_job_lookup_by_recording(env):
    sid = _new_mv_session(env).json()["id"]
    front = _upload(env.client, sid, "front").json()
    side = _upload(env.client, sid, "side").json()
    with env.SessionLocal() as db:
        for rec, view, cadence in ((front, "front", 100.0), (side, "side", 104.0)):
            job = models.AnalysisJob(session_id=sid, subject_id=env.subject_id, recording_id=rec["id"], status="completed")
            db.add(job)
            db.commit()
            db.add(models.AssessmentRecord(
                subject_id=env.subject_id, session_id=sid, recording_id=rec["id"], job_id=job.id,
                overall_status="supported",
                assessment_data={"context": {"camera_view": view}, "feature_interpretations": [
                    {"feature_name": "cadence_steps_per_min", "value": cadence, "unit": "steps/min",
                     "status": "supported", "confidence": 0.8}]},
            ))
            db.commit()

    a = env.client.get(f"/api/v1/sessions/{sid}/assessment", params={"recording_id": front["id"]}).json()
    assert a["recording_id"] == front["id"]
    j = env.client.get(f"/api/v1/sessions/{sid}/job", params={"recording_id": side["id"]}).json()
    assert j["recording_id"] == side["id"]

    mv = env.client.get(f"/api/v1/sessions/{sid}/multiview").json()
    assert {v["camera_view"]: v["status"] for v in mv["views"]}["front"] == "analysed"
    cad = next(m for m in mv["combined"]["measurements"] if m["feature_name"] == "cadence_steps_per_min")
    # 100 vs 104 within tolerance -> value from preferred (side) view, not the mean (102).
    assert cad["status"] == "combined"
    assert cad["value"] == 104.0
    assert cad["source_view"] == "side"
    assert cad["method"] == "single_view_selection"
    assert mv["combined"]["status"] == "partial"  # rear view still missing


# --------------------------------------------------------------------------- #
# Combination policy (pure unit tests)                                        #
# --------------------------------------------------------------------------- #

def _view(view, measurements, mismatch=False, rec_id=None):
    return {"camera_view": view, "recording": {"id": rec_id or f"rec-{view}"},
            "assessment": {"view_mismatch": mismatch, "measurements": measurements}}


def _m(name, value, conf=0.8, status="supported", unit=""):
    return {"feature_name": name, "value": value, "confidence": conf, "status": status, "unit": unit}


def test_eligible_view_mapping():
    assert eligible_views_for_metric("left_knee_flexion_extension_rom") == ("side",)
    assert eligible_views_for_metric("trunk_lateral_displacement_px") == ("front", "rear")
    assert eligible_views_for_metric("cadence")[0] == "side"
    assert eligible_views_for_metric("mystery_metric") is None


def test_never_averages_and_detects_conflict():
    out = combine_measurements([_view("front", [_m("cadence", 90.0)]), _view("side", [_m("cadence", 120.0)])])
    cad = out["measurements"][0]
    assert cad["status"] == "conflicting"
    assert cad["value"] is None


def test_sagittal_metric_only_from_side_view():
    out = combine_measurements([_view("front", [_m("knee_flexion_rom", 30.0)])])
    m = out["measurements"][0]
    assert m["status"] == "insufficient_data"
    assert m["value"] is None

    out = combine_measurements([_view("front", [_m("knee_flexion_rom", 30.0)]),
                                _view("side", [_m("knee_flexion_rom", 55.0)])])
    m = out["measurements"][0]
    assert (m["status"], m["value"], m["source_view"]) == ("combined", 55.0, "side")


def test_low_confidence_mismatch_and_unknown_metrics_excluded():
    out = combine_measurements([
        _view("side", [_m("cadence", 100.0, conf=0.3)]),
        _view("rear", [_m("cadence", 100.0)], mismatch=True),
        _view("front", [_m("weird_metric", 5.0)]),
    ])
    cad = next(m for m in out["measurements"] if m["feature_name"] == "cadence")
    assert cad["status"] == "insufficient_data"
    assert [n["feature_name"] for n in out["not_combined"]] == ["weird_metric"]


def test_summary_includes_legacy_unlabelled_recording():
    now = datetime.utcnow()
    session = SimpleNamespace(id="s1", subject_id="sub", selected_views=None, assessment_mode=None,
                              session_status="active", created_at=now)
    rec = SimpleNamespace(id="r1", camera_view=None, recording_source="upload", original_filename="a.mp4",
                          recorded_at=None, created_at=now, duration_seconds=None, fps=None, width=None, height=None,
                          file_size_bytes=1, validation_status="pending", validation_message=None,
                          quality_status=None, measurement_confidence=None, annotation_status="pending",
                          recording_metadata=None, is_superseded=False)
    out = build_multiview_summary(session, None, [rec], lambda _: None, lambda _: None)
    assert out["assessment_mode"] == "single_view"
    assert out["recording_status"] == "not_applicable"
    assert out["views"] == []
    assert out["unlabelled_recordings"][0]["id"] == "r1"


# --------------------------------------------------------------------------- #
# Backward compatibility                                                      #
# --------------------------------------------------------------------------- #

def test_legacy_single_view_flow_unchanged(env):
    env.as_user("mv_clin")
    sess = env.client.post(f"/api/v1/subjects/{env.subject_id}/sessions", json={"camera_view": "side"}).json()
    assert sess["assessment_mode"] is None
    assert sess["selected_views"] is None
    rec = _upload(env.client, sess["id"])  # no view metadata, like the existing upload page
    assert rec.status_code == 201
    body = rec.json()
    assert body["camera_view"] is None
    assert body["recording_source"] == "upload"
    r = env.client.post(f"/api/v1/sessions/{sess['id']}/analysis", json={"recording_id": body["id"], "camera_view": "side"})
    assert r.status_code == 202


def test_migration_adds_columns_to_legacy_database():
    from src.database import database as dbmod

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "legacy.db"
        con = sqlite3.connect(db_path)
        con.execute("CREATE TABLE sessions (id TEXT PRIMARY KEY, subject_id TEXT NOT NULL, camera_view TEXT, "
                    "is_deleted BOOLEAN, created_at DATETIME)")
        con.execute("CREATE TABLE recordings (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, server_filename TEXT NOT NULL, "
                    "file_path TEXT NOT NULL, validation_status TEXT, is_deleted BOOLEAN, created_at DATETIME)")
        con.execute("INSERT INTO recordings (id, session_id, server_filename, file_path, validation_status, is_deleted) "
                    "VALUES ('old', 's', 'f', 'p', 'passed', 0)")
        con.commit()
        con.close()

        saved = (dbmod._engine, dbmod._SessionLocal)
        try:
            engine = dbmod.init_db(f"sqlite:///{db_path}")
            engine.dispose()
            dbmod._engine.dispose()
        finally:
            dbmod._engine, dbmod._SessionLocal = saved

        con = sqlite3.connect(db_path)
        rec_cols = {r[1] for r in con.execute("PRAGMA table_info(recordings)")}
        sess_cols = {r[1] for r in con.execute("PRAGMA table_info(sessions)")}
        assert {"camera_view", "recording_source", "recorded_at", "recording_metadata",
                "is_superseded", "superseded_at", "superseded_by_id"} <= rec_cols
        assert {"assessment_mode", "selected_views", "client_request_id"} <= sess_cols
        assert con.execute("SELECT is_superseded FROM recordings WHERE id='old'").fetchone()[0] == 0
        con.close()


def test_webm_metadata_extracted():
    import cv2
    import numpy as np
    from src.video.video_validator import extract_video_metadata

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "clip.webm"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"VP80"), 25.0, (320, 240))
        if not writer.isOpened():
            pytest.skip("OpenCV build cannot write VP8/WebM")
        for i in range(50):
            writer.write(np.full((240, 320, 3), i * 4 % 255, dtype=np.uint8))
        writer.release()
        meta, issues = extract_video_metadata(path)
        assert meta is not None
        assert not [i for i in issues if i.severity == "critical"]
        assert meta.frame_count > 0
        assert 1.5 <= meta.duration_seconds <= 2.5
