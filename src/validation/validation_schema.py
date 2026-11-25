"""Pydantic schemas and dataclasses for Milestone 4 Biomechanical Validation."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FeatureCompatibilityDefinition(BaseModel):
    """Specification of compatibility between video feature and NPZ reference variable."""

    feature_name: str
    reference_var: str
    anatomical_definition: str
    movement_plane: str  # "sagittal", "frontal", "transverse", "spatiotemporal"
    video_units: str
    reference_units: str
    units_compatible: bool
    required_camera_view: str  # "side", "front", "rear", "any"
    positive_direction_meaning: str
    negative_direction_meaning: str
    compatibility_status: str  # "directly_comparable", "conditionally_comparable", "not_comparable", "not_testable"
    calibration_required: bool
    known_limitations: List[str] = Field(default_factory=list)


class MatchedObservation(BaseModel):
    """Observation comparing a video-derived measurement with a reference NPZ measurement."""

    observation_id: str
    participant_id: str
    reference_trial_id: str
    video_recording_id: str
    condition: str
    camera_view: str
    feature_name: str
    units: str
    video_value: Optional[float] = None
    reference_value: Optional[float] = None
    video_measurement_method: str
    reference_source: str
    pose_model: str
    pose_version: str
    calibration_status: str
    confidence: float
    qc_status: str
    compatibility_status: str
    is_excluded: bool = False
    exclusion_reason: Optional[str] = None


class EventValidationMetrics(BaseModel):
    """Metrics assessing agreement of event detection against reference timing."""

    event_type: str
    side: Optional[str] = None
    tolerance_ms: float
    total_reference_events: int
    total_detected_events: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    timing_mae_ms: Optional[float] = None
    timing_median_error_ms: Optional[float] = None
    timing_rmse_ms: Optional[float] = None
    timing_error_sd_ms: Optional[float] = None
    status: str = "evaluated"


class AgreementMetrics(BaseModel):
    """Standard statistical agreement metrics between paired measurements."""

    feature_name: str
    camera_view: str
    condition: str
    units: str
    n_observations: int
    n_participants: int
    mean_bias: Optional[float] = None
    mae: Optional[float] = None
    rmse: Optional[float] = None
    pearson_r: Optional[float] = None
    pearson_p_value: Optional[float] = None
    spearman_rho: Optional[float] = None
    spearman_p_value: Optional[float] = None
    bland_altman_lower_loa: Optional[float] = None
    bland_altman_upper_loa: Optional[float] = None
    bland_altman_sd: Optional[float] = None
    bootstrap_mae_ci_lower: Optional[float] = None
    bootstrap_mae_ci_upper: Optional[float] = None
    interpretation_note: str = ""


class CurveValidationSummary(BaseModel):
    """Comparison of 101-point gait-cycle curves between video and reference."""

    feature_name: str
    reference_var: str
    condition: str
    camera_view: str
    n_paired_cycles: int
    mean_curve_mae: Optional[float] = None
    mean_curve_rmse: Optional[float] = None
    mean_curve_bias: Optional[float] = None
    peak_magnitude_diff_mean: Optional[float] = None
    peak_timing_diff_mean_pct: Optional[float] = None
    pointwise_mae_curve: List[Optional[float]] = Field(default_factory=list)
    pointwise_bias_curve: List[Optional[float]] = Field(default_factory=list)
