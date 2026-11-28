"""Factory for instantiating pose estimation engines."""

from typing import Optional
import torch

from src.core.logging import get_logger
from src.pose_estimation.base_pose_estimator import BasePoseEstimator
from src.pose_estimation.synthetic_estimator import SyntheticPoseEstimator
from src.pose_estimation.yolo_estimator import YOLOPoseEstimator

logger = get_logger(__name__)


def create_pose_estimator(
    estimator_type: str = "yolo",
    device: Optional[str] = None,
    model_path: str = "yolov8n-pose.pt",
) -> BasePoseEstimator:
    """
    Factory function returning a configured pose estimator.
    Automatically checks and selects CUDA if available and requested.
    """
    if device is None:
        device = "cuda:0" if torch.cuda.is_available() else "cpu"

    est_lower = estimator_type.lower()
    if est_lower in {"yolo", "ultralytics"}:
        logger.info("Initializing YOLOPoseEstimator on %s", device)
        return YOLOPoseEstimator(model_path=model_path, device=device)
    elif est_lower in {"mediapipe", "mediapipe_pose"}:
        # Explicitly requested: fail loudly rather than silently substituting YOLO,
        # so stored results always reflect the model that actually produced them.
        from src.pose_estimation.mediapipe_estimator import MediaPipePoseEstimator
        logger.info("Initializing MediaPipePoseEstimator on cpu")
        return MediaPipePoseEstimator()
    elif est_lower in {"synthetic", "mock", "test"}:
        logger.info("Initializing SyntheticPoseEstimator on %s", device)
        return SyntheticPoseEstimator(device=device)
    else:
        logger.warning("Estimator '%s' unrecognized, defaulting to YOLOPoseEstimator", estimator_type)
        return YOLOPoseEstimator(model_path=model_path, device=device)
