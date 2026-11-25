"""Mock / MediaPipe-compatible Landmark Pose Estimator for deterministic testing and fallback."""

from typing import Dict, Optional
import numpy as np

from src.pose_estimation.base_pose_estimator import BasePoseEstimator
from src.pose_estimation.landmark_schema import FramePose, Landmark, STANDARD_LANDMARKS


class SyntheticPoseEstimator(BasePoseEstimator):
    """
    Deterministic pose estimator generating geometrically consistent biomechanical walking pose.
    Ideal for testing pipelines without downloading external model weights or when hardware is restricted.
    """

    def __init__(self, device: str = "cpu", model_name: str = "synthetic_gait_generator") -> None:
        super().__init__(device=device, model_name=model_name)

    def estimate_frame(
        self,
        frame_bgr: np.ndarray,
        frame_index: int,
        timestamp_s: float,
        orig_width: int,
        orig_height: int,
    ) -> FramePose:
        w, h = orig_width, orig_height
        cx, cy = w * 0.5, h * 0.5
        t = timestamp_s

        # Generate walking kinematics oscillation (1.0 Hz cadence = 60 steps/min)
        phase = 2.0 * np.pi * 1.0 * t
        l_knee_flex = np.sin(phase)
        r_knee_flex = np.sin(phase + np.pi)

        landmarks: Dict[str, Landmark] = {}
        points = {
            "nose": (cx, cy - 200),
            "left_shoulder": (cx - 40, cy - 140),
            "right_shoulder": (cx + 40, cy - 140),
            "left_elbow": (cx - 60, cy - 80),
            "right_elbow": (cx + 60, cy - 80),
            "left_wrist": (cx - 70, cy - 20),
            "right_wrist": (cx + 70, cy - 20),
            "left_hip": (cx - 30, cy),
            "right_hip": (cx + 30, cy),
            "left_knee": (cx - 35, cy + 90 + l_knee_flex * 15),
            "right_knee": (cx + 35, cy + 90 + r_knee_flex * 15),
            "left_ankle": (cx - 40, cy + 180 + l_knee_flex * 20),
            "right_ankle": (cx + 40, cy + 180 + r_knee_flex * 20),
            "left_heel": (cx - 45, cy + 195 + l_knee_flex * 20),
            "right_heel": (cx + 45, cy + 195 + r_knee_flex * 20),
            "left_foot_index": (cx - 20, cy + 200 + l_knee_flex * 18),
            "right_foot_index": (cx + 20, cy + 200 + r_knee_flex * 18),
        }

        for name, (x, y) in points.items():
            x_norm = max(0.0, min(1.0, x / w))
            y_norm = max(0.0, min(1.0, y / h))
            landmarks[name] = Landmark(
                name=name,
                x_px=round(x, 2),
                y_px=round(y, 2),
                x_norm=round(x_norm, 4),
                y_norm=round(y_norm, 4),
                confidence=0.95,
                is_visible=True,
            )

        return FramePose(
            frame_index=frame_index,
            timestamp_s=timestamp_s,
            model_name=self.model_name,
            model_version="1.0.0",
            device=self.device,
            image_width=orig_width,
            image_height=orig_height,
            landmarks=landmarks,
        )
