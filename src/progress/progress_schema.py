from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid
from datetime import datetime


class ProgressCategory(str, Enum):
    improvement = "improvement"
    deterioration = "deterioration"
    no_meaningful_change = "no_meaningful_change"
    insufficient_evidence = "insufficient_evidence"


class ComparabilityDecision(str, Enum):
    comparable = "comparable"
    conditionally_comparable = "conditionally_comparable"
    not_comparable = "not_comparable"
    insufficient_data = "insufficient_data"


class FeatureChange(BaseModel):
    feature_name: str
    baseline_value: Optional[float] = None
    current_value: Optional[float] = None
    absolute_change: Optional[float] = None
    relative_change_pct: Optional[float] = None
    baseline_sd: Optional[float] = None
    change_in_sd_units: Optional[float] = None
    category: ProgressCategory
    comparability: ComparabilityDecision
    comparability_note: str = ""
    confidence: float = 0.0


class Baseline(BaseModel):
    baseline_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subject_id: str
    version: int = 1
    n_sessions: int = 0
    n_trials: int = 0
    feature_means: Dict[str, Optional[float]] = Field(default_factory=dict)
    feature_medians: Dict[str, Optional[float]] = Field(default_factory=dict)
    feature_sds: Dict[str, Optional[float]] = Field(default_factory=dict)
    feature_n: Dict[str, int] = Field(default_factory=dict)
    contributing_session_ids: List[str] = Field(default_factory=list)
    conditions: List[str] = Field(default_factory=list)
    context_summary: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    is_current: bool = True


class ProgressReport(BaseModel):
    progress_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    subject_id: str
    current_session_id: str
    comparison_type: str  # "baseline", "previous_session", "selected_session"
    comparison_session_id: Optional[str] = None
    baseline_id: Optional[str] = None
    feature_changes: List[FeatureChange] = Field(default_factory=list)
    overall_category: ProgressCategory
    comparability_issues: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
