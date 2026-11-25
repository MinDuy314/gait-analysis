"""Common standardized landmark schema for pose estimators."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

# Standardized landmark names across models
STANDARD_LANDMARKS = [
    "nose",
    "left_eye", "right_eye",
    "left_ear", "right_ear",
    "left_shoulder", "right_shoulder",
    "left_elbow", "right_elbow",
    "left_wrist", "right_wrist",
    "left_hip", "right_hip",
    "left_knee", "right_knee",
    "left_ankle", "right_ankle",
    "left_heel", "right_heel",
    "left_foot_index", "right_foot_index",
]


class Landmark(BaseModel):
    """Standardized single joint/anatomical landmark."""

    name: str
    x_px: float
    y_px: float
    z_px: Optional[float] = None
    x_norm: float
    y_norm: float
    confidence: float
    is_visible: bool = True


class FramePose(BaseModel):
    """Collection of detected landmarks for a single frame."""

    frame_index: int
    timestamp_s: float
    model_name: str
    model_version: str
    device: str
    image_width: int
    image_height: int
    landmarks: Dict[str, Landmark] = Field(default_factory=dict)
