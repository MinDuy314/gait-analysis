from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel
from datetime import datetime

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    skip: int
    limit: int


class SubjectResponse(BaseModel):
    id: str
    display_name: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    id: str
    subject_id: str
    camera_view: Optional[str] = None
    walking_speed_ms: Optional[float] = None
    walking_surface: Optional[str] = None
    height_m: Optional[float] = None
    mass_kg: Optional[float] = None
    session_status: Optional[str] = "active"
    summary: Optional[str] = None
    notes: Optional[str] = None
    assessment_mode: Optional[str] = None
    selected_views: Optional[List[str]] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class RecordingResponse(BaseModel):
    id: str
    session_id: str
    server_filename: str
    file_size_bytes: Optional[int] = None
    validation_status: str
    annotated_video_path: Optional[str] = None
    annotation_status: Optional[str] = None
    quality_status: Optional[str] = None
    measurement_confidence: Optional[float] = None
    analysis_warnings: Optional[List[str]] = None
    original_filename: Optional[str] = None
    validation_message: Optional[str] = None
    duration_seconds: Optional[float] = None
    fps: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    camera_view: Optional[str] = None
    recording_source: Optional[str] = None
    recorded_at: Optional[datetime] = None
    recording_metadata: Optional[dict] = None
    is_superseded: Optional[bool] = False
    superseded_at: Optional[datetime] = None
    superseded_by_id: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class JobResponse(BaseModel):
    id: str
    session_id: str
    subject_id: str
    recording_id: Optional[str] = None
    status: str
    current_stage: Optional[str] = None
    progress_pct: float = 0.0
    processed_frames: int = 0
    total_frames: int = 0
    error_message: Optional[str] = None
    retry_count: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class ReportResponse(BaseModel):
    id: str
    report_type: str
    title: Optional[str] = None
    subject_id: str
    session_id: str
    assessment_id: Optional[str] = None
    status: str
    clinician_notes: Optional[str] = None
    rehabilitation_priorities: Optional[List[str]] = None
    recommendations: Optional[str] = None
    report_data: Optional[dict] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    revision_history: Optional[List[dict]] = None
    generated_at: datetime
    updated_at: Optional[datetime] = None
    model_config = {"from_attributes": True}
