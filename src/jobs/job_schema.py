"""Job schema definitions."""
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    partially_completed = "partially_completed"
    failed = "failed"
    cancelled = "cancelled"


class JobCreate(BaseModel):
    session_id: str
    recording_id: Optional[str] = None
    camera_view: str = "side"
    pose_model: str = "yolo"


class JobDetail(BaseModel):
    id: str
    session_id: str
    subject_id: str
    recording_id: Optional[str] = None
    status: JobStatus
    current_stage: Optional[str] = None
    progress_pct: float = 0.0
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    pose_model: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    result_data: Optional[Dict[str, Any]] = None
