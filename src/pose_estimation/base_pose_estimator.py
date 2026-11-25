"""Abstract base class for modular pose estimators."""

from abc import ABC, abstractmethod
from typing import Optional
import numpy as np

from src.pose_estimation.landmark_schema import FramePose


class BasePoseEstimator(ABC):
    """Abstract interface for pose estimators (YOLO, MediaPipe, etc.)."""

    def __init__(self, device: str = "cpu", model_name: str = "base") -> None:
        self.device = device
        self.model_name = model_name

    @abstractmethod
    def estimate_frame(
        self,
        frame_bgr: np.ndarray,
        frame_index: int,
        timestamp_s: float,
        orig_width: int,
        orig_height: int,
    ) -> FramePose:
        """Estimate 2D landmarks on a single image frame."""
        pass
