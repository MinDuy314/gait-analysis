"""Video metadata and quality assessment schemas."""

from typing import List, Optional
from pydantic import BaseModel, Field


class VideoMetadata(BaseModel):
    """Metadata extracted from a video file."""

    filename: str
    file_path: str
    file_size_bytes: int
    duration_seconds: float
    frame_count: int
    fps: float
    width: int
    height: int
    aspect_ratio: float
    codec: str
    is_readable: bool
    has_variable_fps: bool = False


class QualityIssue(BaseModel):
    """Specific quality issue encountered in recording or extraction."""

    issue_code: str
    severity: str  # "info", "warning", "critical"
    message: str


class VideoValidationResult(BaseModel):
    """Validation report for an ingested video."""

    is_valid: bool
    metadata: Optional[VideoMetadata] = None
    issues: List[QualityIssue] = Field(default_factory=list)
