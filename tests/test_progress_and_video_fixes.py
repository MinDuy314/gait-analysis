"""Regression tests for monotonic progress calculation, frame clamping, and video playback API contract."""
from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

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
from src.database.database import Base
from src.database.models import AnalysisJob, Recording, Session as DbSession, Subject, User
from src.database.repositories import JobRepository
from src.jobs.job_manager import JobManager
from src.jobs.task_registry import PIPELINE_STAGES, run_analysis_pipeline
from src.pose_estimation.landmark_schema import FramePose
from src.video.frame_extractor import ExtractedFrame
from src.video.video_metadata import VideoMetadata
from src.visualization.video_annotator import annotate_video


@pytest.fixture
def env_setup():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    patient_a = User(
        id=str(uuid.uuid4()),
        username="patient_prog_a",
        hashed_password=hash_password("pw"),
        role="individual",
        organization_id="org_prog",
    )
    patient_b = User(
        id=str(uuid.uuid4()),
        username="patient_prog_b",
        hashed_password=hash_password("pw"),
        role="individual",
        organization_id="org_prog",
    )
    db.add_all([patient_a, patient_b])
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
        "patient_a": patient_a,
        "patient_b": patient_b,
        "SessionLocal": SessionLocal,
    }

    jm.wait_all(timeout=5.0)
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _make_sample_mp4(path: Path, frames: int = 8, width: int = 128, height: int = 96) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (width, height))
    for i in range(frames):
        img = np.zeros((height, width, 3), dtype=np.uint8)
        img[:, :, i % 3] = 180
        writer.write(img)
    writer.release()
    return path


def test_pipeline_progress_is_monotonic_never_exceeds_100_and_includes_annotation(env_setup, tmp_path):
    """Verify overall progress_pct strictly advances forward, stays < 100 while running,
    distinguishes frame processing from annotation, and hits 100 only on completion."""
    db = env_setup["db"]
    repo = JobRepository(db)

    sub = Subject(id="sub_mono", owner_id=env_setup["patient_a"].id, organization_id="org_prog")
    db.add(sub)
    sess = DbSession(id="sess_mono", subject_id=sub.id)
    db.add(sess)
    video_path = _make_sample_mp4(tmp_path / "mono.mp4", frames=6)
    rec = Recording(
        id="rec_mono",
        session_id=sess.id,
        server_filename="mono.mp4",
        file_path=str(video_path),
        validation_status="pending",
    )
    db.add(rec)
    job = repo.create(session_id=sess.id, subject_id=sub.id, recording_id=rec.id)
    db.commit()

    recorded_updates = []
    orig_update = JobRepository.update_status

    def spy_update(self, job_id, status, stage=None, progress=None, error=None, result=None, processed_frames=None, total_frames=None):
        recorded_updates.append((status, stage, progress, processed_frames, total_frames))
        return orig_update(
            self,
            job_id,
            status,
            stage=stage,
            progress=progress,
            error=error,
            result=result,
            processed_frames=processed_frames,
            total_frames=total_frames,
        )

    with patch.object(JobRepository, "update_status", spy_update):
        run_analysis_pipeline(
            job_id=job.id,
            db=db,
            recording_path=str(video_path),
            session_id=sess.id,
            subject_id=sub.id,
            pose_model="synthetic",
            recording_id=rec.id,
        )

    assert len(recorded_updates) >= 8
    progresses = [u[2] for u in recorded_updates if u[2] is not None]
    stages = [u[1] for u in recorded_updates]

    # Monotonically non-decreasing: never moves backwards!
    assert progresses == sorted(progresses), f"Progress moved backwards: {progresses}"
    # Every running update stays < 100.0
    running_progresses = [u[2] for u in recorded_updates if u[0] == "running" and u[2] is not None]
    assert all(0.0 <= p < 100.0 for p in running_progresses), f"Running progress reached 100 prematurely: {running_progresses}"
    # Final completed update is 100.0
    assert recorded_updates[-1][0] == "completed"
    assert recorded_updates[-1][2] == 100.0
    # Annotation stage is explicitly tracked before finalize
    assert "annotate_recording" in stages
    assert stages.index("annotate_recording") < stages.index("finalize")


def test_frame_count_clamping_when_metadata_undercounts(tmp_path):
    """If container metadata under-reports frame_count, total_frames adjusts so processed <= total."""
    from src.video.video_pipeline_runner import process_video_pipeline
    from src.view_detection.camera_view_classifier import ViewClassificationResult

    video_path = tmp_path / "undercount.mp4"
    video_path.touch()

    meta = VideoMetadata(
        filename="undercount.mp4",
        file_path=str(video_path),
        file_size_bytes=500,
        duration_seconds=0.2,
        frame_count=3,  # Metadata says 3, actual reader yields 5
        fps=30.0,
        width=64,
        height=48,
        aspect_ratio=64 / 48,
        codec="mp4v",
        is_readable=True,
    )
    mock_val = MagicMock(is_valid=True, metadata=meta)
    mock_view = ViewClassificationResult(predicted_view="side", confidence=0.9)
    mock_clf = MagicMock()
    mock_clf.classify_sequence.return_value = mock_view
    frames = [ExtractedFrame(i, i * 0.033, np.zeros((48, 64, 3), dtype=np.uint8), 64, 48) for i in range(5)]
    pose = FramePose(frame_index=0, timestamp_s=0.0, model_name="yolo", model_version="v8", device="cpu", image_width=64, image_height=48, landmarks={})
    est = MagicMock(model_name="yolo", device="cpu")
    est.estimate_frame.return_value = pose

    calls = []
    with patch("src.video.video_pipeline_runner.validate_video", return_value=mock_val), \
         patch("src.video.video_pipeline_runner.create_pose_estimator", return_value=est), \
         patch("src.video.video_pipeline_runner.extract_frames", return_value=iter(frames)), \
         patch("src.video.video_pipeline_runner.CameraViewClassifier", return_value=mock_clf), \
         patch("src.video.video_pipeline_runner.detect_gait_events_from_poses", return_value=[]), \
         patch("src.video.video_pipeline_runner.segment_gait_cycles", return_value=[]), \
         patch("src.video.video_pipeline_runner.extract_video_features", return_value=[]):
        process_video_pipeline(video_path=video_path, progress_callback=lambda p, t: calls.append((p, t)))

    assert calls == [(1, 3), (2, 3), (3, 3), (4, 4), (5, 5)]
    assert all(p <= t for p, t in calls)


def test_recordings_list_shape_browser_codec_and_rbac_video_access(env_setup, tmp_path):
    """Verify recordings list endpoint returns array consumed by frontend, H.264 MP4 is written
    when supported, and RBAC protects video streaming."""
    client = env_setup["client"]
    db = env_setup["db"]
    patient_a = env_setup["patient_a"]
    patient_b = env_setup["patient_b"]

    token_a = create_access_token(data={"sub": patient_a.id, "role": patient_a.role})
    client.headers["Authorization"] = f"Bearer {token_a}"

    sub = Subject(id="sub_rec_list", owner_id=patient_a.id, organization_id="org_prog")
    db.add(sub)
    sess = DbSession(id="sess_rec_list", subject_id=sub.id)
    db.add(sess)
    db.commit()

    src = _make_sample_mp4(tmp_path / "walk.mp4", frames=6, width=128, height=96)
    with open(src, "rb") as f:
        up = client.post(f"/api/v1/sessions/{sess.id}/recordings", files={"file": ("walk.mp4", f, "video/mp4")})
    assert up.status_code == 201
    rec_id = up.json()["id"]

    # Frontend relies on GET /sessions/{id}/recordings returning an array
    list_res = client.get(f"/api/v1/sessions/{sess.id}/recordings")
    assert list_res.status_code == 200
    items = list_res.json()
    assert isinstance(items, list)
    assert len(items) == 1
    assert items[0]["id"] == rec_id

    # Run analysis via API
    sub_job = client.post(
        f"/api/v1/sessions/{sess.id}/analysis",
        json={"recording_id": rec_id, "camera_view": "side", "pose_model": "synthetic"},
    )
    assert sub_job.status_code == 202
    job_id = sub_job.json()["id"]
    env_setup["jm"].wait_all(timeout=15.0)

    job_data = client.get(f"/api/v1/jobs/{job_id}").json()
    assert job_data["status"] == "completed"
    assert job_data["recording_id"] == rec_id
    assert job_data["progress_pct"] == 100.0

    # List recordings again: annotation_status must be completed & file valid
    rec_list_after = client.get(f"/api/v1/sessions/{sess.id}/recordings").json()
    assert rec_list_after[0]["annotation_status"] == "completed"
    ann_path = Path(rec_list_after[0]["annotated_video_path"])
    assert ann_path.exists() and ann_path.stat().st_size > 0

    # Verify authenticated MP4 fetch
    vid_res = client.get(f"/api/v1/recordings/{rec_id}/annotated-video")
    assert vid_res.status_code == 200
    assert vid_res.headers["content-type"] == "video/mp4"
    assert len(vid_res.content) == ann_path.stat().st_size

    # Verify RBAC isolation: Patient B gets 403
    token_b = create_access_token(data={"sub": patient_b.id, "role": patient_b.role})
    client.headers["Authorization"] = f"Bearer {token_b}"
    assert client.get(f"/api/v1/recordings/{rec_id}/annotated-video").status_code == 403
    assert client.get(f"/api/v1/sessions/{sess.id}/recordings").status_code == 403
