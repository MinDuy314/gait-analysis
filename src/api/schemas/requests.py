from typing import Optional
from pydantic import BaseModel


class SubjectCreate(BaseModel):
    display_name: Optional[str] = None


class SubjectUpdate(BaseModel):
    display_name: Optional[str] = None


class SessionCreate(BaseModel):
    walking_speed_ms: Optional[float] = None
    walking_surface: Optional[str] = None
    slope_deg: Optional[float] = None
    walking_direction: Optional[str] = None
    footwear: Optional[str] = None
    camera_view: Optional[str] = None
    calibration_status: Optional[str] = None
    height_m: Optional[float] = None
    mass_kg: Optional[float] = None
    notes: Optional[str] = None


class AnalysisRequest(BaseModel):
    recording_id: Optional[str] = None
    camera_view: str = "side"
    pose_model: str = "yolo"


class ReportRequest(BaseModel):
    report_type: str = "individual"  # "individual" or "professional"
    title: Optional[str] = None
    clinician_notes: Optional[str] = None
    rehabilitation_priorities: Optional[list[str]] = None
    recommendations: Optional[str] = None


class ReportUpdateRequest(BaseModel):
    title: Optional[str] = None
    clinician_notes: Optional[str] = None
    rehabilitation_priorities: Optional[list[str]] = None
    recommendations: Optional[str] = None
    status: Optional[str] = None  # "draft" or "pending_review"


class AssessmentUpdateRequest(BaseModel):
    clinical_interpretation: Optional[str] = None
    clinical_notes: Optional[str] = None
    approval_status: Optional[str] = None  # "pending_review" or "approved"


class CompareSessionsRequest(BaseModel):
    session_id_1: str
    session_id_2: str
