"""MediaPipe Pose Landmarker adapter (33 landmarks, including heel and toe).

Unlike YOLO (COCO-17), MediaPipe tracks ``left/right_heel`` and ``left/right_foot_index``
(big-toe region), which gait-cycle analysis uses for initial contact, toe-off and heel
rise. Runs on CPU (also on macOS). Model file: Google's ``pose_landmarker_full.task``.
"""

from pathlib import Path
from typing import Dict, Optional

import cv2
import numpy as np

from src.core.logging import get_logger
from src.pose_estimation.base_pose_estimator import BasePoseEstimator
from src.pose_estimation.landmark_schema import FramePose, Landmark

logger = get_logger(__name__)

MODEL_FILENAME = "pose_landmarker_full.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
)
MODEL_VERSION = "pose_landmarker_full (float16)"

# MediaPipe Pose landmark index -> standardized name (only names used by the app).
MP_LANDMARKS = {
    0: "nose",
    2: "left_eye", 5: "right_eye",
    7: "left_ear", 8: "right_ear",
    11: "left_shoulder", 12: "right_shoulder",
    13: "left_elbow", 14: "right_elbow",
    15: "left_wrist", 16: "right_wrist",
    23: "left_hip", 24: "right_hip",
    25: "left_knee", 26: "right_knee",
    27: "left_ankle", 28: "right_ankle",
    29: "left_heel", 30: "right_heel",
    31: "left_foot_index", 32: "right_foot_index",
}


def default_model_path() -> Path:
    from src.core.config import AppConfig
    return AppConfig().project_root / "models" / "mediapipe" / MODEL_FILENAME


class MediaPipePoseEstimator(BasePoseEstimator):
    """Single-person MediaPipe Pose Landmarker in VIDEO mode (temporal tracking)."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        visibility_threshold: float = 0.5,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        super().__init__(device="cpu", model_name="mediapipe_pose_landmarker_full")
        path = Path(model_path) if model_path else default_model_path()
        if not path.exists():
            raise FileNotFoundError(
                f"MediaPipe pose model not found at {path}. Download it from {MODEL_URL} "
                f"into {path.parent}."
            )
        try:
            from mediapipe.tasks.python import BaseOptions, vision
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise ImportError("mediapipe is not installed; run `pip install mediapipe`.") from exc

        self._mp_image_cls = __import__("mediapipe").Image
        self._mp_format = __import__("mediapipe").ImageFormat.SRGB
        options = vision.PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(path)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)
        self.visibility_threshold = visibility_threshold
        self.model_version = MODEL_VERSION
        self._last_ms = -1

    def close(self) -> None:
        if getattr(self, "_landmarker", None) is not None:
            self._landmarker.close()
            self._landmarker = None

    def __del__(self):  # pragma: no cover - best effort cleanup
        try:
            self.close()
        except Exception:
            pass

    def estimate_frame(
        self,
        frame_bgr: np.ndarray,
        frame_index: int,
        timestamp_s: float,
        orig_width: int,
        orig_height: int,
    ) -> FramePose:
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = self._mp_image_cls(image_format=self._mp_format, data=np.ascontiguousarray(rgb))
        # VIDEO mode requires strictly increasing timestamps.
        ts_ms = max(int(round(timestamp_s * 1000)), self._last_ms + 1)
        self._last_ms = ts_ms
        result = self._landmarker.detect_for_video(image, ts_ms)

        landmarks: Dict[str, Landmark] = {}
        if result.pose_landmarks:
            person = result.pose_landmarks[0]
            for idx, name in MP_LANDMARKS.items():
                lm = person[idx]
                vis = float(lm.visibility if lm.visibility is not None else 0.0)
                x_norm, y_norm = float(lm.x), float(lm.y)
                # Pixel coordinates in the processed frame's space, matching the YOLO adapter.
                landmarks[name] = Landmark(
                    name=name,
                    x_px=round(x_norm * w, 2),
                    y_px=round(y_norm * h, 2),
                    z_px=round(float(lm.z) * w, 2),
                    x_norm=round(min(1.0, max(0.0, x_norm)), 4),
                    y_norm=round(min(1.0, max(0.0, y_norm)), 4),
                    confidence=round(vis, 3),
                    is_visible=vis >= self.visibility_threshold,
                )

        return FramePose(
            frame_index=frame_index,
            timestamp_s=timestamp_s,
            model_name=self.model_name,
            model_version=self.model_version,
            device=self.device,
            image_width=orig_width,
            image_height=orig_height,
            landmarks=landmarks,
        )
