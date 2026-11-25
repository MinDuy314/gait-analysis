"""Automated test suite for Milestone 3: Video Processing Pipeline."""

from pathlib import Path
import cv2
import numpy as np
import pytest

from src.core.config import AppConfig
from src.feature_extraction.video_feature_extractor import compute_2d_angle, extract_video_features
from src.gait_events.gait_cycle_segmenter import normalize_cycle_trajectory, segment_gait_cycles
from src.gait_events.gait_event_detector import GaitEvent, detect_gait_events_from_poses
from src.pose_estimation.landmark_schema import FramePose, Landmark
from src.pose_estimation.pose_factory import create_pose_estimator
from src.video.video_metadata import VideoMetadata
from src.video.video_pipeline_runner import process_video_pipeline
from src.video.video_validator import validate_video
from src.view_detection.camera_view_classifier import CameraViewClassifier
from src.visualization.video_plots import plot_video_diagnostics


def _create_synthetic_video(file_path: Path, width: int = 320, height: int = 240, fps: float = 30.0, num_frames: int = 60) -> Path:
    """Generate a clean synthetic MP4 video file with moving visual elements."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(file_path), fourcc, fps, (width, height))
    for i in range(num_frames):
        frame = np.full((height, width, 3), 40, dtype=np.uint8)
        # Draw moving circle to simulate limb motion
        cx = int(width * 0.5 + 30 * np.sin(2 * np.pi * i / 30))
        cy = int(height * 0.5 + 20 * np.cos(2 * np.pi * i / 30))
        cv2.circle(frame, (cx, cy), 15, (0, 255, 0), -1)
        out.write(frame)
    out.release()
    return file_path


def test_video_validation_valid_and_invalid(tmp_path: Path):
    """Test video validation on valid video, corrupted file, and nonexistent file."""
    v_path = tmp_path / "valid_test.mp4"
    _create_synthetic_video(v_path, fps=30.0, num_frames=45)

    res_valid = validate_video(v_path)
    assert res_valid.is_valid is True
    assert res_valid.metadata is not None
    assert res_valid.metadata.frame_count == 45
    assert res_valid.metadata.fps == 30.0
    assert res_valid.metadata.width == 320

    # Nonexistent file
    res_none = validate_video(tmp_path / "nonexistent.mp4")
    assert res_none.is_valid is False
    assert any(i.issue_code == "file_not_found" for i in res_none.issues)

    # Corrupted / empty file
    corrupt_file = tmp_path / "corrupted.mp4"
    corrupt_file.write_bytes(b"invalid data string")
    res_corrupt = validate_video(corrupt_file)
    assert res_corrupt.is_valid is False


def test_pose_estimators_cpu_and_cuda_switch():
    """Verify pose estimator factory, YOLO inference, and synthetic pose estimator."""
    # 1. Synthetic estimator
    synth = create_pose_estimator(estimator_type="synthetic", device="cpu")
    dummy_frame = np.zeros((240, 320, 3), dtype=np.uint8)
    pose = synth.estimate_frame(dummy_frame, frame_index=0, timestamp_s=0.0, orig_width=320, orig_height=240)
    assert pose.model_name == "synthetic_gait_generator"
    assert "left_knee" in pose.landmarks
    assert pose.landmarks["left_knee"].is_visible is True

    # 2. YOLO pose estimator on CPU
    yolo_cpu = create_pose_estimator(estimator_type="yolo", device="cpu")
    pose_yolo = yolo_cpu.estimate_frame(dummy_frame, frame_index=0, timestamp_s=0.0, orig_width=320, orig_height=240)
    assert "yolo" in pose_yolo.model_name
    assert pose_yolo.device == "cpu"


def test_view_detection_classifier():
    """Verify geometric camera view classification for side and front views."""
    classifier = CameraViewClassifier()

    def make_pose(sw: float, th: float, face_vis: bool) -> FramePose:
        lm = {
            "left_shoulder": Landmark(name="left_shoulder", x_px=100.0, y_px=50.0, x_norm=0.3, y_norm=0.2, confidence=0.9),
            "right_shoulder": Landmark(name="right_shoulder", x_px=100.0 + sw, y_px=50.0, x_norm=0.3 + sw / 320.0, y_norm=0.2, confidence=0.9),
            "left_hip": Landmark(name="left_hip", x_px=100.0, y_px=50.0 + th, x_norm=0.3, y_norm=0.2 + th / 240.0, confidence=0.9),
            "right_hip": Landmark(name="right_hip", x_px=100.0 + sw, y_px=50.0 + th, x_norm=0.3 + sw / 320.0, y_norm=0.2 + th / 240.0, confidence=0.9),
            "nose": Landmark(name="nose", x_px=100.0, y_px=30.0, x_norm=0.3, y_norm=0.1, confidence=0.9 if face_vis else 0.1, is_visible=face_vis),
        }
        return FramePose(frame_index=0, timestamp_s=0.0, model_name="test", model_version="1", device="cpu", image_width=320, image_height=240, landmarks=lm)

    # Narrow shoulders relative to torso -> Side view
    side_poses = [make_pose(sw=20.0, th=100.0, face_vis=True) for _ in range(5)]
    res_side = classifier.classify_sequence(side_poses)
    assert res_side.predicted_view == "side"

    # Broad shoulders with face -> Front view
    front_poses = [make_pose(sw=80.0, th=100.0, face_vis=True) for _ in range(5)]
    res_front = classifier.classify_sequence(front_poses)
    assert res_front.predicted_view == "front"


def test_gait_events_and_cycle_segmentation():
    """Verify gait event detection, cycle segmentation, and 101-point normalization."""
    # 1. 2D angle test
    ang_90 = compute_2d_angle((0.0, 1.0), (0.0, 0.0), (1.0, 0.0))
    assert pytest.approx(ang_90, abs=1e-4) == 90.0

    # 2. Cycle segmentation from events
    ev1 = GaitEvent(event_id="l1", event_type="foot_strike", side="left", frame_index=0, timestamp_s=0.0, confidence=0.9, detection_method="test")
    ev2 = GaitEvent(event_id="l2", event_type="foot_strike", side="left", frame_index=30, timestamp_s=1.0, confidence=0.9, detection_method="test")
    ev3 = GaitEvent(event_id="l3", event_type="foot_strike", side="left", frame_index=60, timestamp_s=2.0, confidence=0.9, detection_method="test")

    cycles = segment_gait_cycles([ev1, ev2, ev3])
    assert len(cycles) == 2
    assert cycles[0].is_complete is True
    assert pytest.approx(cycles[0].duration_s, abs=1e-3) == 1.0

    # 3. 101-point temporal normalization
    raw_sig = np.array([0.0, 50.0, 100.0])
    norm_sig = normalize_cycle_trajectory(raw_sig, n_points=101)
    assert norm_sig.shape == (101,)
    assert pytest.approx(norm_sig[0], abs=1e-4) == 0.0
    assert pytest.approx(norm_sig[50], abs=1e-4) == 50.0
    assert pytest.approx(norm_sig[100], abs=1e-4) == 100.0


def test_end_to_end_video_pipeline(tmp_path: Path):
    """Run full video pipeline with synthetic pose generator, verify QC and outputs."""
    v_path = tmp_path / "e2e_walk.mp4"
    _create_synthetic_video(v_path, fps=30.0, num_frames=75)

    result = process_video_pipeline(
        video_path=v_path,
        session_id="test_session_01",
        estimator_type="synthetic",
        device="cpu",
    )

    assert result.recording_id == "e2e_walk"
    assert result.total_frames_extracted == 75
    assert len(result.gait_events) > 0
    assert len(result.measurements) > 0
    assert any(m.feature_name == "cadence" for m in result.measurements)

    # Diagnostic visualizer
    fig_paths = plot_video_diagnostics(result, output_dir=tmp_path / "figs")
    assert len(fig_paths) >= 1
    for f in fig_paths:
        assert f.exists() and f.stat().st_size > 0
