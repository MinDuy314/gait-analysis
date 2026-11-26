"""Tests for frame-level progress tracking during video pose estimation and job lifecycle."""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from src.database.database import Base, init_db
from src.database.models import User, Subject, Session, Recording, AnalysisJob
from src.database.repositories import JobRepository, SubjectRepository, SessionRepository
from src.video.video_pipeline_runner import process_video_pipeline
from src.video.frame_extractor import ExtractedFrame
from src.pose_estimation.landmark_schema import FramePose
from src.jobs.task_registry import run_analysis_pipeline
from src.api.main import app
from src.api.dependencies import get_db, get_job_manager
from src.api.auth.security import create_access_token


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    yield db
    db.close()
    engine.dispose()


@pytest.fixture
def auth_client(test_db):
    user = User(
        id="user_test_frames",
        username="frame_tester",
        hashed_password="pw",
        role="individual",
        organization_id="org_test",
    )
    test_db.add(user)
    test_db.commit()

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    token = create_access_token(data={"sub": user.id, "role": user.role, "user_id": user.id})
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {token}"
    yield client, user, test_db
    app.dependency_overrides.clear()


def test_job_model_and_repository_frame_progress(test_db):
    repo = JobRepository(test_db)
    job = repo.create(session_id="sess_1", subject_id="subj_1")
    assert job.processed_frames == 0
    assert job.total_frames == 0

    repo.update_status(
        job.id,
        "running",
        stage="estimate_pose",
        progress=25.0,
        processed_frames=10,
        total_frames=40,
    )
    refreshed = repo.get(job.id)
    assert refreshed.status == "running"
    assert refreshed.current_stage == "estimate_pose"
    assert refreshed.progress_pct == 25.0
    assert refreshed.processed_frames == 10
    assert refreshed.total_frames == 40


def test_job_api_exposes_frame_progress(auth_client):
    client, user, db = auth_client
    subj = Subject(id="subj_frames", owner_id=user.id, organization_id="org_test")
    db.add(subj)
    sess = Session(id="sess_frames", subject_id=subj.id)
    db.add(sess)
    job = AnalysisJob(
        id="job_frames_123",
        session_id=sess.id,
        subject_id=subj.id,
        status="running",
        current_stage="estimate_pose",
        progress_pct=45.5,
        processed_frames=45,
        total_frames=100,
    )
    db.add(job)
    db.commit()

    resp = client.get(f"/api/v1/jobs/{job.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "job_frames_123"
    assert data["status"] == "running"
    assert data["current_stage"] == "estimate_pose"
    assert data["progress_pct"] == 45.5
    assert data["processed_frames"] == 45
    assert data["total_frames"] == 100


def test_video_pipeline_runner_calls_progress_callback(tmp_path):
    # Mock video validation & frame extraction
    video_path = tmp_path / "mock_walk.mp4"
    video_path.touch()

    from src.video.video_metadata import VideoMetadata
    from src.view_detection.camera_view_classifier import ViewClassificationResult

    mock_metadata = VideoMetadata(
        filename="mock_walk.mp4",
        file_path=str(video_path),
        file_size_bytes=1000,
        duration_seconds=0.16,
        fps=30.0,
        frame_count=5,
        width=640,
        height=480,
        aspect_ratio=640 / 480,
        codec="mp4v",
        is_readable=True,
    )
    mock_val_result = MagicMock()
    mock_val_result.is_valid = True
    mock_val_result.metadata = mock_metadata

    mock_view_res = ViewClassificationResult(
        predicted_view="side",
        confidence=0.9,
    )
    mock_classifier = MagicMock()
    mock_classifier.classify_sequence.return_value = mock_view_res

    mock_frames = [
        ExtractedFrame(
            frame_index=i,
            timestamp_s=i * 0.033,
            image_bgr=MagicMock(),
            orig_width=640,
            orig_height=480,
        )
        for i in range(5)
    ]

    mock_pose = FramePose(
        frame_index=0,
        timestamp_s=0.0,
        model_name="yolo",
        model_version="v8",
        device="cpu",
        image_width=640,
        image_height=480,
        landmarks={},
    )
    mock_estimator = MagicMock()
    mock_estimator.estimate_frame.return_value = mock_pose
    mock_estimator.model_name = "mock_yolo"
    mock_estimator.device = "cpu"

    progress_calls = []

    def tracking_callback(processed, total):
        progress_calls.append((processed, total))

    with patch("src.video.video_pipeline_runner.validate_video", return_value=mock_val_result), \
         patch("src.video.video_pipeline_runner.create_pose_estimator", return_value=mock_estimator), \
         patch("src.video.video_pipeline_runner.extract_frames", return_value=iter(mock_frames)), \
         patch("src.video.video_pipeline_runner.CameraViewClassifier", return_value=mock_classifier), \
         patch("src.video.video_pipeline_runner.detect_gait_events_from_poses", return_value=[]), \
         patch("src.video.video_pipeline_runner.segment_gait_cycles", return_value=[]), \
         patch("src.video.video_pipeline_runner.extract_video_features", return_value=[]):
        
        res = process_video_pipeline(
            video_path=video_path,
            progress_callback=tracking_callback,
        )

        assert res.total_frames_extracted == 5
        assert len(progress_calls) == 5
        assert progress_calls == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]


def test_pipeline_task_registry_updates_real_frames(test_db, tmp_path):
    repo = JobRepository(test_db)
    job = repo.create(session_id="sess_mock", subject_id="subj_mock")
    video_path = tmp_path / "walk.mp4"
    video_path.touch()

    mock_val_result = MagicMock()
    mock_val_result.is_valid = True
    mock_val_result.issues = []
    mock_val_result.metadata.total_frames = 4
    mock_val_result.metadata.fps = 30.0
    mock_val_result.metadata.duration_seconds = 0.13
    mock_val_result.metadata.width = 640
    mock_val_result.metadata.height = 480

    mock_pipeline_res = MagicMock()
    mock_pipeline_res.poses = [
        FramePose(
            frame_index=i,
            timestamp_s=0.0,
            model_name="yolo",
            model_version="v8",
            device="cpu",
            image_width=640,
            image_height=480,
            landmarks={},
        )
        for i in range(4)
    ]
    mock_pipeline_res.gait_cycles = []
    mock_pipeline_res.camera_view.predicted_view = "side_left"
    mock_pipeline_res.measurements = []

    def mock_process_video(video_path, session_id, estimator_type, progress_callback=None):
        if progress_callback:
            for i in range(1, 5):
                progress_callback(i, 4)
        return mock_pipeline_res

    with patch("src.video.video_validator.validate_video", return_value=mock_val_result), \
         patch("src.video.video_pipeline_runner.process_video_pipeline", side_effect=mock_process_video):
        
        run_analysis_pipeline(
            job_id=job.id,
            db=test_db,
            recording_path=str(video_path),
            session_id="sess_mock",
            subject_id="subj_mock",
        )

    completed_job = repo.get(job.id)
    assert completed_job.status == "completed"
    assert completed_job.progress_pct == 100.0
    assert completed_job.processed_frames == 4
    assert completed_job.total_frames == 4


def test_pipeline_failure_records_error_state(test_db, tmp_path):
    repo = JobRepository(test_db)
    job = repo.create(session_id="sess_fail", subject_id="subj_fail")
    video_path = tmp_path / "broken.mp4"
    video_path.touch()

    mock_val_result = MagicMock()
    mock_val_result.is_valid = False
    issue = MagicMock()
    issue.message = "File corrupt"
    issue.severity = "critical"
    issue.model_dump.return_value = {"message": "File corrupt", "severity": "critical"}
    mock_val_result.issues = [issue]

    with patch("src.video.video_validator.validate_video", return_value=mock_val_result):
        run_analysis_pipeline(
            job_id=job.id,
            db=test_db,
            recording_path=str(video_path),
            session_id="sess_fail",
            subject_id="subj_fail",
        )

    failed_job = repo.get(job.id)
    assert failed_job.status == "failed"
    assert failed_job.current_stage == "validate_recording"
    assert "Video validation failed: File corrupt" in failed_job.error_message
