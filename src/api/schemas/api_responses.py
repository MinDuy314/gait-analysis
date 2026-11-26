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
    created_at: datetime
    model_config = {"from_attributes": True}


class JobResponse(BaseModel):
    id: str
    session_id: str
    subject_id: str
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
    subject_id: str
    session_id: str
    status: str
    generated_at: datetime
    model_config = {"from_attributes": True}
