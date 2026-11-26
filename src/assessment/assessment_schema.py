from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


class AssessmentStatus(str, Enum):
    supported = "supported"
    limited_evidence = "limited_evidence"
    insufficient_data = "insufficient_data"
    not_assessable = "not_assessable"


class ComparabilityStatus(str, Enum):
    comparable = "comparable"
    conditionally_comparable = "conditionally_comparable"
    not_comparable = "not_comparable"
    insufficient_data = "insufficient_data"


class GaitCategory(str, Enum):
    temporal = "temporal"
    spatial = "spatial"
    kinematic = "kinematic"
    symmetry = "symmetry"
    postural = "postural"


class UncertaintySource(BaseModel):
    source: str
    description: str
    severity: str  # "low", "medium", "high"


class FeatureInterpretation(BaseModel):
    feature_name: str
    category: Optional[str] = None
    value: Optional[float] = None
    unit: str = ""
    status: AssessmentStatus
    rule_name: Optional[str] = None
    interpretation_text: str
    evidence_sources: List[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    limitations: List[str] = Field(default_factory=list)
    uncertainty_sources: List[UncertaintySource] = Field(default_factory=list)


class ReferenceComparison(BaseModel):
    feature_name: str
    value: Optional[float] = None
    reference_median: Optional[float] = None
    reference_sd: Optional[float] = None
    percentile_position: Optional[float] = None
    z_score: Optional[float] = None
    n_reference: int = 0
    condition: str = ""
    comparability: ComparabilityStatus = ComparabilityStatus.insufficient_data
    note: str = ""


class BilateralResult(BaseModel):
    feature_name: str
    primary_value: Optional[float] = None
    contra_value: Optional[float] = None
    absolute_difference: Optional[float] = None
    symmetry_index: Optional[float] = None
    confidence: float = 0.0
    side_mapping_verified: bool = False
    interpretation: str = ""
    limitations: List[str] = Field(default_factory=list)


class AssessmentContext(BaseModel):
    subject_id: str
    session_id: str
    camera_view: Optional[str] = None
    walking_speed_ms: Optional[float] = None
    walking_surface: Optional[str] = None
    slope_deg: Optional[float] = None
    walking_direction: Optional[str] = None
    footwear: Optional[str] = None
    height_m: Optional[float] = None
    mass_kg: Optional[float] = None
    calibration_status: Optional[str] = None
    pose_model: str = "unknown"
    pose_model_version: str = "unknown"
    feature_extraction_version: str = "1.0.0"
    assessment_rule_version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class GaitAssessment(BaseModel):
    assessment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    context: AssessmentContext
    overall_status: AssessmentStatus
    feature_interpretations: List[FeatureInterpretation] = Field(default_factory=list)
    grouped_measurements: Dict[str, List[FeatureInterpretation]] = Field(default_factory=dict)
    reference_comparisons: List[ReferenceComparison] = Field(default_factory=list)
    bilateral_results: List[BilateralResult] = Field(default_factory=list)
    unsupported_features: List[str] = Field(default_factory=list)
    global_limitations: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
