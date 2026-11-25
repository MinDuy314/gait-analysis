"""Ultralytics YOLO Pose estimator adapter with CPU/GPU support."""

from typing import Dict, Optional
import numpy as np
from ultralytics import YOLO

from src.core.logging import get_logger
from src.pose_estimation.base_pose_estimator import BasePoseEstimator
from src.pose_estimation.landmark_schema import FramePose, Landmark

logger = get_logger(__name__)

# COCO 17 Keypoints map for YOLO
COCO_KEYPOINTS = [
    "nose",            # 0
    "left_eye",        # 1
    "right_eye",       # 2
    "left_ear",        # 3
    "right_ear",       # 4
    "left_shoulder",   # 5
    "right_shoulder",  # 6
    "left_elbow",      # 7
    "right_elbow",     # 8
    "left_wrist",      # 9
    "right_wrist",     # 10
    "left_hip",        # 11
    "right_hip",       # 12
    "left_knee",       # 13
    "right_knee",      # 14
    "left_ankle",      # 15
    "right_ankle",     # 16
]


class YOLOPoseEstimator(BasePoseEstimator):
    """Pose estimation using Ultralytics YOLO models."""

    def __init__(
        self,
        model_path: str = "yolov8n-pose.pt",
        device: str = "cpu",
        conf_threshold: float = 0.25,
    ) -> None:
        super().__init__(device=device, model_name=f"yolo_{model_path}")
        self.conf_threshold = conf_threshold
        try:
            self.model = YOLO(model_path)
        except Exception as exc:
            logger.warning("Failed to load %s on %s directly, falling back: %s", model_path, device, exc)
            self.model = YOLO("yolov8n-pose.pt")

    def estimate_frame(
        self,
        frame_bgr: np.ndarray,
        frame_index: int,
        timestamp_s: float,
        orig_width: int,
        orig_height: int,
    ) -> FramePose:
        """Run YOLO inference on a single frame and convert to standardized FramePose."""
        # Execute with device handling and automatic CPU fallback
        try:
            results = self.model(frame_bgr, device=self.device, verbose=False)
        except Exception as exc:
            logger.warning("GPU execution failed (%s), falling back to CPU", exc)
            self.device = "cpu"
            results = self.model(frame_bgr, device="cpu", verbose=False)

        h, w = frame_bgr.shape[:2]
        landmarks_dict: Dict[str, Landmark] = {}

        if results and len(results) > 0 and results[0].keypoints is not None:
            kp_obj = results[0].keypoints
            # Extract coordinates for highest-confidence person if multiple detections
            if len(kp_obj.data) > 0:
                # Keypoints tensor: [persons, 17, 3] -> (x, y, conf)
                best_person = kp_obj.data[0].cpu().numpy()
                for idx, name in enumerate(COCO_KEYPOINTS):
                    x, y, conf = float(best_person[idx][0]), float(best_person[idx][1]), float(best_person[idx][2])
                    x_norm = max(0.0, min(1.0, x / w)) if w > 0 else 0.0
                    y_norm = max(0.0, min(1.0, y / h)) if h > 0 else 0.0
                    vis = conf >= self.conf_threshold

                    landmarks_dict[name] = Landmark(
                        name=name,
                        x_px=round(x, 2),
                        y_px=round(y, 2),
                        x_norm=round(x_norm, 4),
                        y_norm=round(y_norm, 4),
                        confidence=round(conf, 3),
                        is_visible=vis,
                    )

                # Approximate foot markers from ankle if model lacks separate heel/toe
                if "left_ankle" in landmarks_dict:
                    la = landmarks_dict["left_ankle"]
                    landmarks_dict["left_heel"] = Landmark(
                        name="left_heel",
                        x_px=la.x_px,
                        y_px=la.y_px,
                        x_norm=la.x_norm,
                        y_norm=la.y_norm,
                        confidence=la.confidence * 0.9,
                        is_visible=la.is_visible,
                    )
                if "right_ankle" in landmarks_dict:
                    ra = landmarks_dict["right_ankle"]
                    landmarks_dict["right_heel"] = Landmark(
                        name="right_heel",
                        x_px=ra.x_px,
                        y_px=ra.y_px,
                        x_norm=ra.x_norm,
                        y_norm=ra.y_norm,
                        confidence=ra.confidence * 0.9,
                        is_visible=ra.is_visible,
                    )

        return FramePose(
            frame_index=frame_index,
            timestamp_s=timestamp_s,
            model_name=self.model_name,
            model_version="8.4.216",
            device=self.device,
            image_width=orig_width,
            image_height=orig_height,
            landmarks=landmarks_dict,
        )
