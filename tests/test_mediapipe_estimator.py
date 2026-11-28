"""MediaPipe pose estimator adapter (Feature 02 follow-up: heel/toe tracking)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.pose_estimation import mediapipe_estimator as mpe

MODEL_PRESENT = mpe.default_model_path().exists()
needs_model = pytest.mark.skipif(not MODEL_PRESENT, reason="MediaPipe model file not downloaded")


def _fake_landmark(x, y, vis=0.9):
    return SimpleNamespace(x=x, y=y, z=-0.1, visibility=vis)


def _estimator_with_fake_result(person):
    est = mpe.MediaPipePoseEstimator.__new__(mpe.MediaPipePoseEstimator)
    est.device, est.model_name, est.model_version = "cpu", "mediapipe_pose_landmarker_full", mpe.MODEL_VERSION
    est.visibility_threshold, est._last_ms = 0.5, -1
    est._mp_image_cls = lambda image_format, data: data
    est._mp_format = None
    est._landmarker = MagicMock()
    est._landmarker.detect_for_video.return_value = SimpleNamespace(pose_landmarks=[person] if person else [])
    return est


def test_maps_heel_and_toe_to_standard_names():
    person = [_fake_landmark(0.5, 0.5, 0.2) for _ in range(33)]
    person[29] = _fake_landmark(0.25, 0.9)   # left heel
    person[31] = _fake_landmark(0.30, 0.95)  # left foot index
    person[27] = _fake_landmark(0.26, 0.85)  # left ankle
    est = _estimator_with_fake_result(person)
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    pose = est.estimate_frame(frame, 3, 0.1, 1280, 720)
    heel, toe, ankle = pose.landmarks["left_heel"], pose.landmarks["left_foot_index"], pose.landmarks["left_ankle"]
    assert (heel.x_px, heel.y_px) == (320.0, 648.0)
    assert (toe.x_px, toe.y_px) == (384.0, 684.0)
    assert heel.x_px != ankle.x_px  # real heel, not an ankle proxy
    assert heel.is_visible and not pose.landmarks["nose"].is_visible  # visibility 0.2 < 0.5
    assert set(mpe.MP_LANDMARKS.values()) == set(pose.landmarks)
    assert pose.model_version == mpe.MODEL_VERSION


def test_video_mode_timestamps_strictly_increase():
    est = _estimator_with_fake_result(None)
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    for ts in (0.0, 0.0, 0.0004, 0.04):
        est.estimate_frame(frame, 0, ts, 10, 10)
    sent = [c.args[1] for c in est._landmarker.detect_for_video.call_args_list]
    assert sent == sorted(set(sent)) and len(sent) == 4


def test_no_person_returns_empty_pose():
    est = _estimator_with_fake_result(None)
    pose = est.estimate_frame(np.zeros((10, 10, 3), dtype=np.uint8), 0, 0.0, 10, 10)
    assert pose.landmarks == {}


def test_missing_model_file_raises_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="Download it from"):
        mpe.MediaPipePoseEstimator(model_path=str(tmp_path / "missing.task"))


@needs_model
def test_factory_and_real_model_on_blank_frame():
    from src.pose_estimation.pose_factory import create_pose_estimator
    est = create_pose_estimator("mediapipe")
    assert isinstance(est, mpe.MediaPipePoseEstimator) and est.device == "cpu"
    pose = est.estimate_frame(np.zeros((480, 640, 3), dtype=np.uint8), 0, 0.0, 640, 480)
    assert pose.landmarks == {}  # no person in a blank frame -> nothing invented
    est.close()


def test_analysis_request_pose_model_validation():
    from pydantic import ValidationError
    from src.api.schemas.requests import AnalysisRequest
    assert AnalysisRequest(pose_model="MediaPipe").pose_model == "mediapipe"
    assert AnalysisRequest().pose_model == "yolo"
    with pytest.raises(ValidationError):
        AnalysisRequest(pose_model="openpose")
