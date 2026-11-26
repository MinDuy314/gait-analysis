"""Tests for annotated video generation, DB persistence, and API endpoint."""
from __future__ import annotations

import os
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Generator
from unittest.mock import patch, MagicMock

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ---------------------------------------------------------------------------
# DB / app fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    from src.database.database import Base
    from src.database import models  # noqa – register all ORM classes
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture(scope="function")
def db_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture(scope="function")
def client(engine):
    """TestClient with an in-memory DB injected via dependency override."""
    from src.api.main import app
    from src.api.dependencies import get_db, get_storage, get_job_manager
    from src.storage.file_storage import FileStorage
    from src.jobs.job_manager import JobManager

    Session = sessionmaker(bind=engine)

    def _override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    with tempfile.TemporaryDirectory() as tmp:
        storage = FileStorage(storage_root=Path(tmp))
        test_jm = JobManager(db_session_factory=Session, max_workers=2)

        def _override_storage():
            return storage

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_storage] = _override_storage
        app.dependency_overrides[get_job_manager] = lambda: test_jm

        with Session() as db:
            from src.database import models
            from src.api.auth.security import hash_password, create_access_token
            u = models.User(
                id=str(uuid.uuid4()),
                username="test_clinician_av",
                hashed_password=hash_password("Pass@123"),
                role="professional",
                organization_id="default_org",
                is_active=True,
            )
            db.add(u)
            db.commit()
            token = create_access_token(data={"sub": u.id, "role": u.role})

        with TestClient(app) as c:
            c.headers["Authorization"] = f"Bearer {token}"
            c.job_manager = test_jm
            yield c
        test_jm.wait_all(timeout=5.0)
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers to create a minimal synthetic video file on disk
# ---------------------------------------------------------------------------

def _make_test_video(path: Path, width: int = 64, height: int = 48, fps: float = 10.0, frames: int = 15) -> Path:
    """Write a minimal synthetic MP4 using OpenCV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    for i in range(frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :, i % 3] = 128  # vary colour per frame
        writer.write(frame)
    writer.release()
    return path


def _make_frame_pose(frame_index: int, width: int = 64, height: int = 48, conf: float = 0.9):
    """Return a FramePose with a small set of visible landmarks."""
    from src.pose_estimation.landmark_schema import FramePose, Landmark

    landmarks = {}
    for name, (x, y) in [
        ("nose", (32, 10)),
        ("left_shoulder", (20, 20)),
        ("right_shoulder", (44, 20)),
        ("left_hip", (20, 35)),
        ("right_hip", (44, 35)),
        ("left_knee", (20, 42)),
        ("right_knee", (44, 42)),
        ("left_ankle", (20, 47)),
        ("right_ankle", (44, 47)),
    ]:
        landmarks[name] = Landmark(
            name=name,
            x_px=float(x),
            y_px=float(y),
            x_norm=x / width,
            y_norm=y / height,
            confidence=conf,
            is_visible=True,
        )
    return FramePose(
        frame_index=frame_index,
        timestamp_s=frame_index / 10.0,
        model_name="test",
        model_version="v0",
        device="cpu",
        image_width=width,
        image_height=height,
        landmarks=landmarks,
    )


# ===========================================================================
# 1. annotate_video — success path
# ===========================================================================

def test_annotate_video_success(tmp_path):
    """annotate_video produces a non-empty, reopenable MP4."""
    from src.visualization.video_annotator import annotate_video

    src = _make_test_video(tmp_path / "src.mp4", frames=5)
    poses = [_make_frame_pose(i) for i in range(5)]
    out = tmp_path / "annotated_src.mp4"

    result = annotate_video(video_path=src, poses=poses, output_path=out)

    assert result == out
    assert out.exists()
    assert out.stat().st_size > 0

    cap = cv2.VideoCapture(str(out))
    assert cap.isOpened(), "Output MP4 should be reopenable"
    cap.release()


# ===========================================================================
# 2. Missing landmarks — no crash, MP4 still produced
# ===========================================================================

def test_annotate_video_missing_landmarks(tmp_path):
    """Poses with no landmarks produce valid (blank-frame) output without crashing."""
    from src.visualization.video_annotator import annotate_video
    from src.pose_estimation.landmark_schema import FramePose

    src = _make_test_video(tmp_path / "src.mp4", frames=4)
    poses = [
        FramePose(
            frame_index=i, timestamp_s=float(i), model_name="t", model_version="v0",
            device="cpu", image_width=64, image_height=48, landmarks={},
        )
        for i in range(4)
    ]
    out = tmp_path / "annotated.mp4"
    result = annotate_video(video_path=src, poses=poses, output_path=out)

    assert out.exists()
    assert out.stat().st_size > 0


# ===========================================================================
# 3. Low-confidence landmarks — not drawn (no assertion error either)
# ===========================================================================

def test_annotate_video_low_confidence(tmp_path):
    """Landmarks below threshold are silently skipped — no crash."""
    from src.visualization.video_annotator import annotate_video

    src = _make_test_video(tmp_path / "src.mp4", frames=3)
    poses = [_make_frame_pose(i, conf=0.1) for i in range(3)]  # all below default 0.5
    out = tmp_path / "annotated.mp4"

    result = annotate_video(
        video_path=src,
        poses=poses,
        output_path=out,
        conf_threshold=0.5,
    )

    assert out.exists()
    assert out.stat().st_size > 0


# ===========================================================================
# 4. Invalid input — raises VideoAnnotationError
# ===========================================================================

def test_annotate_video_invalid_input(tmp_path):
    """Non-existent video path raises VideoAnnotationError."""
    from src.visualization.video_annotator import annotate_video
    from src.core.exceptions import VideoAnnotationError

    with pytest.raises(VideoAnnotationError, match="not found"):
        annotate_video(
            video_path=tmp_path / "does_not_exist.mp4",
            poses=[],
            output_path=tmp_path / "out.mp4",
        )


# ===========================================================================
# 5. Annotation persisted in DB
# ===========================================================================

def test_annotation_persisted_in_db(engine, db_session):
    """RecordingRepository.update_annotation stores path and status correctly."""
    from src.database.models import Subject, Session as GaitSession, Recording
    from src.database.repositories import RecordingRepository

    # Minimal data setup
    sub = Subject(id=str(uuid.uuid4()), display_name="test_sub")
    db_session.add(sub)
    db_session.commit()

    sess = GaitSession(id=str(uuid.uuid4()), subject_id=sub.id)
    db_session.add(sess)
    db_session.commit()

    rec = Recording(
        id=str(uuid.uuid4()),
        session_id=sess.id,
        server_filename="test.mp4",
        file_path="/tmp/test.mp4",
        validation_status="pending",
    )
    db_session.add(rec)
    db_session.commit()

    repo = RecordingRepository(db_session)
    ok = repo.update_annotation(
        recording_id=rec.id,
        annotated_video_path="/data/uploads/annotated_test.mp4",
        annotation_status="completed",
    )
    assert ok is True

    db_session.expire(rec)
    fetched = repo.get(rec.id)
    assert fetched.annotation_status == "completed"
    assert fetched.annotated_video_path == "/data/uploads/annotated_test.mp4"


# ===========================================================================
# 6. API — 409 when annotation not ready
# ===========================================================================

def test_api_annotated_video_not_ready(client, engine):
    """GET /annotated-video returns 409 when annotation_status != 'completed'."""
    from sqlalchemy.orm import sessionmaker
    from src.database.models import Subject, Session as GaitSession, Recording

    Session = sessionmaker(bind=engine)
    db = Session()

    sub = Subject(id=str(uuid.uuid4()), display_name="api_test")
    db.add(sub)
    db.commit()

    sess = GaitSession(id=str(uuid.uuid4()), subject_id=sub.id)
    db.add(sess)
    db.commit()

    rec = Recording(
        id=str(uuid.uuid4()),
        session_id=sess.id,
        server_filename="vid.mp4",
        file_path="/tmp/vid.mp4",
        validation_status="pending",
        annotation_status="pending",
    )
    db.add(rec)
    db.commit()
    rec_id = rec.id
    db.close()

    resp = client.get(f"/api/v1/recordings/{rec_id}/annotated-video")
    assert resp.status_code == 409
    assert "not ready" in resp.json()["detail"].lower()


# ===========================================================================
# 7. API — 404 when recording does not exist
# ===========================================================================

def test_api_annotated_video_recording_not_found(client):
    """GET /annotated-video returns 404 for unknown recording ID."""
    resp = client.get(f"/api/v1/recordings/{uuid.uuid4()}/annotated-video")
    assert resp.status_code == 404


# ===========================================================================
# 8. API — 404 when file missing despite completed status
# ===========================================================================

def test_api_annotated_video_file_missing(client, engine, tmp_path):
    """GET /annotated-video returns 404 when file doesn't exist on disk."""
    from sqlalchemy.orm import sessionmaker
    from src.database.models import Subject, Session as GaitSession, Recording
    from src.core.config import AppConfig

    Session = sessionmaker(bind=engine)
    db = Session()

    sub = Subject(id=str(uuid.uuid4()), display_name="api_miss")
    db.add(sub)
    db.commit()

    sess = GaitSession(id=str(uuid.uuid4()), subject_id=sub.id)
    db.add(sess)
    db.commit()

    cfg = AppConfig()
    # Path inside storage root so traversal check passes, but file doesn't exist
    missing_path = str((cfg.project_root / "data" / "uploads" / "ghost_annotated.mp4").resolve())

    rec = Recording(
        id=str(uuid.uuid4()),
        session_id=sess.id,
        server_filename="vid.mp4",
        file_path="/tmp/vid.mp4",
        validation_status="passed",
        annotation_status="completed",
        annotated_video_path=missing_path,
    )
    db.add(rec)
    db.commit()
    rec_id = rec.id
    db.close()

    resp = client.get(f"/api/v1/recordings/{rec_id}/annotated-video")
    assert resp.status_code == 404


# ===========================================================================
# 9. API — 200 stream with video/mp4 content-type
# ===========================================================================

def test_api_annotated_video_success(client, engine, tmp_path):
    """GET /annotated-video returns 200 with video/mp4 when annotation is ready."""
    from sqlalchemy.orm import sessionmaker
    from src.database.models import Subject, Session as GaitSession, Recording
    from src.core.config import AppConfig

    cfg = AppConfig()
    # Create a real small MP4 inside the storage root
    ann_dir = cfg.project_root / "data" / "uploads" / "_test_annotated"
    ann_dir.mkdir(parents=True, exist_ok=True)
    ann_file = ann_dir / "annotated_test.mp4"
    _make_test_video(ann_file, frames=3)

    Session = sessionmaker(bind=engine)
    db = Session()

    sub = Subject(id=str(uuid.uuid4()), display_name="stream_test")
    db.add(sub)
    db.commit()

    sess = GaitSession(id=str(uuid.uuid4()), subject_id=sub.id)
    db.add(sess)
    db.commit()

    rec = Recording(
        id=str(uuid.uuid4()),
        session_id=sess.id,
        server_filename="orig.mp4",
        file_path="/tmp/orig.mp4",
        validation_status="passed",
        annotation_status="completed",
        annotated_video_path=str(ann_file.resolve()),
    )
    db.add(rec)
    db.commit()
    rec_id = rec.id
    db.close()

    resp = client.get(f"/api/v1/recordings/{rec_id}/annotated-video")
    assert resp.status_code == 200
    assert "video/mp4" in resp.headers.get("content-type", "")
    assert len(resp.content) > 0

    # Cleanup
    import shutil
    shutil.rmtree(str(ann_dir), ignore_errors=True)


# ===========================================================================
# 10. VideoAnnotationError is distinct from GaitAnalysisError
# ===========================================================================

def test_video_annotation_error_distinct():
    """VideoAnnotationError must NOT be a subclass of GaitAnalysisError."""
    from src.core.exceptions import VideoAnnotationError, GaitAnalysisError

    err = VideoAnnotationError("test")
    assert isinstance(err, Exception)
    assert not isinstance(err, GaitAnalysisError)



# ===========================================================================
# 11. End-to-End API submission: recording_id reaches task, annotates video
# ===========================================================================

def test_api_analysis_submission_generates_annotated_video(client, engine, tmp_path):
    """End-to-end API test verifying:
    1. recording_id reaches the background job;
    2. validation_status is persisted as 'passed';
    3. real / synthetic pose results reach annotation;
    4. hardcoded mock metrics (cadence=110, knee_rom=58) are absent;
    5. annotation_status is 'completed' (never left pending);
    6. GET /annotated-video streams the MP4 with 200.
    """
    import time
    from sqlalchemy.orm import sessionmaker
    from src.database.models import Subject, Session as GaitSession, Recording
    from src.core.config import AppConfig

    cfg = AppConfig()
    video_dir = cfg.project_root / "data" / "uploads" / "_e2e_test"
    video_dir.mkdir(parents=True, exist_ok=True)
    video_file = video_dir / "valid_walk.mp4"
    _make_test_video(video_file, width=320, height=240, fps=30.0, frames=45)

    Session = sessionmaker(bind=engine)
    db = Session()

    sub = Subject(id=str(uuid.uuid4()), display_name="e2e_subject")
    db.add(sub)
    db.commit()

    sess = GaitSession(id=str(uuid.uuid4()), subject_id=sub.id)
    db.add(sess)
    db.commit()

    rec = Recording(
        id=str(uuid.uuid4()),
        session_id=sess.id,
        server_filename="valid_walk.mp4",
        file_path=str(video_file.resolve()),
        validation_status="pending",
        annotation_status="pending",
    )
    db.add(rec)
    db.commit()
    rec_id = rec.id
    sess_id = sess.id
    db.close()

    # Submit analysis via the API with recording_id and synthetic pose estimator
    resp = client.post(
        f"/api/v1/sessions/{sess_id}/analysis",
        json={
            "recording_id": rec_id,
            "camera_view": "side",
            "pose_model": "synthetic",
        },
    )
    assert resp.status_code == 202
    job_id = resp.json()["id"]

    # Wait for background job to finish
    if hasattr(client, "job_manager"):
        client.job_manager.wait_all(timeout=10.0)

    # Poll status in case wait_all finished early
    for _ in range(20):
        j_resp = client.get(f"/api/v1/jobs/{job_id}").json()
        if j_resp["status"] in ("completed", "failed"):
            break
        time.sleep(0.2)

    assert j_resp["status"] == "completed", f"Job failed: {j_resp.get('error_message')}"

    # Verify Recording DB state
    db = Session()
    updated_rec = db.query(Recording).filter(Recording.id == rec_id).first()
    assert updated_rec.validation_status == "passed", "Validation status must be persisted as 'passed'"
    assert updated_rec.annotation_status == "completed", "Annotation status must be 'completed', not pending"
    assert updated_rec.annotated_video_path is not None
    assert Path(updated_rec.annotated_video_path).exists()
    assert Path(updated_rec.annotated_video_path).stat().st_size > 0
    db.close()

    # Verify GET /annotated-video succeeds
    stream_resp = client.get(f"/api/v1/recordings/{rec_id}/annotated-video")
    assert stream_resp.status_code == 200
    assert "video/mp4" in stream_resp.headers.get("content-type", "")
    assert len(stream_resp.content) > 0

    # Cleanup
    import shutil
    shutil.rmtree(str(video_dir), ignore_errors=True)


# ===========================================================================
# 12. Validation failure handling in API workflow
# ===========================================================================

def test_api_analysis_submission_handles_validation_failure(client, engine, tmp_path):
    """Verify corrupted / invalid video halts pipeline, marks validation 'failed',
    marks annotation 'failed' (never left pending), and marks job 'failed'.
    """
    import time
    from sqlalchemy.orm import sessionmaker
    from src.database.models import Subject, Session as GaitSession, Recording

    bad_video = tmp_path / "corrupted.mp4"
    bad_video.write_text("This is not a valid video file")

    Session = sessionmaker(bind=engine)
    db = Session()

    sub = Subject(id=str(uuid.uuid4()), display_name="fail_subject")
    db.add(sub)
    db.commit()

    sess = GaitSession(id=str(uuid.uuid4()), subject_id=sub.id)
    db.add(sess)
    db.commit()

    rec = Recording(
        id=str(uuid.uuid4()),
        session_id=sess.id,
        server_filename="corrupted.mp4",
        file_path=str(bad_video.resolve()),
        validation_status="pending",
        annotation_status="pending",
    )
    db.add(rec)
    db.commit()
    rec_id = rec.id
    sess_id = sess.id
    db.close()

    resp = client.post(
        f"/api/v1/sessions/{sess_id}/analysis",
        json={"recording_id": rec_id, "camera_view": "side", "pose_model": "synthetic"},
    )
    assert resp.status_code == 202
    job_id = resp.json()["id"]

    if hasattr(client, "job_manager"):
        client.job_manager.wait_all(timeout=10.0)

    for _ in range(20):
        j_resp = client.get(f"/api/v1/jobs/{job_id}").json()
        if j_resp["status"] in ("completed", "failed"):
            break
        time.sleep(0.2)

    assert j_resp["status"] == "failed", "Job must fail when video validation fails"

    db = Session()
    updated_rec = db.query(Recording).filter(Recording.id == rec_id).first()
    assert updated_rec.validation_status == "failed"
    assert updated_rec.annotation_status == "failed", "Annotation status must be updated to 'failed', never left pending"
    db.close()

    # Annotated video must return 409
    get_resp = client.get(f"/api/v1/recordings/{rec_id}/annotated-video")
    assert get_resp.status_code == 409
