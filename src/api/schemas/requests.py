from typing import List, Optional
from pydantic import BaseModel, field_validator
from pydantic_core import PydanticCustomError

# Camera views supported by multi-view assessment (Feature 01).
CAMERA_VIEWS = ("front", "side", "rear")


def _normalize_views(views: Optional[List[str]]) -> Optional[List[str]]:
    if views is None:
        return None
    cleaned: List[str] = []
    for v in views:
        v_norm = (v or "").strip().lower()
        if v_norm not in CAMERA_VIEWS:
            raise PydanticCustomError(
                "camera_view", "Unsupported camera view. Allowed: front, side, rear"
            )
        if v_norm not in cleaned:
            cleaned.append(v_norm)
    if not cleaned:
        raise PydanticCustomError("camera_view", "At least one camera view must be selected")
    # Keep a stable clinical ordering regardless of selection order.
    return [v for v in CAMERA_VIEWS if v in cleaned]


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
    assessment_mode: Optional[str] = None  # single_view | multi_view
    selected_views: Optional[List[str]] = None
    client_request_id: Optional[str] = None  # idempotency key; repeated submits return the same session

    @field_validator("selected_views")
    @classmethod
    def _validate_views(cls, v):
        return _normalize_views(v)

    @field_validator("assessment_mode")
    @classmethod
    def _validate_mode(cls, v):
        if v is not None and v not in ("single_view", "multi_view"):
            raise PydanticCustomError("assessment_mode", "assessment_mode must be 'single_view' or 'multi_view'")
        return v


class SessionViewsUpdate(BaseModel):
    selected_views: List[str]

    @field_validator("selected_views")
    @classmethod
    def _validate_views(cls, v):
        return _normalize_views(v)


class AnalysisRequest(BaseModel):
    recording_id: Optional[str] = None
    # When omitted, the recording's labelled camera view is used, falling back to "side".
    camera_view: Optional[str] = None
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
