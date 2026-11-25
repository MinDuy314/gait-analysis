import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from src.assessment.assessment_schema import (
    AssessmentContext, AssessmentStatus, GaitAssessment,
)
from src.assessment.biomechanical_rules import build_default_rules
from src.assessment.reference_comparison import ReferenceComparisonEngine
from src.assessment.bilateral_assessment import assess_bilateral_features
from src.assessment.uncertainty_propagation import aggregate_uncertainty
from src.core.config import AppConfig


class AssessmentEngine:
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig()
        self.rules = build_default_rules()
        self.ref_engine = ReferenceComparisonEngine(config=self.config)

    def assess(
        self,
        context: AssessmentContext,
        features: Dict[str, Any],
        confidences: Optional[Dict[str, float]] = None,
        bilateral_features: Optional[Dict[str, Any]] = None,
        n_cycles: int = 0,
        event_confidence: float = 0.5,
        cycle_quality: float = 0.5,
    ) -> GaitAssessment:
        if confidences is None:
            confidences = {}

        camera_view = context.camera_view or "unknown"
        cal_status = context.calibration_status or "uncalibrated"

        # Uncertainty
        feature_conf = float(sum(confidences.values()) / max(len(confidences), 1)) if confidences else 0.5
        landmark_conf = feature_conf
        uncertainty = aggregate_uncertainty(
            landmark_confidence=landmark_conf,
            feature_confidence=feature_conf,
            event_confidence=event_confidence,
            cycle_quality=cycle_quality,
            n_cycles=n_cycles,
            camera_view=camera_view,
            calibration_status=cal_status,
        )

        # Rule-based interpretations
        interpretations = []
        for rule in self.rules:
            result = rule.evaluate(features, camera_view, confidences)
            if result is not None:
                interpretations.append(result)

        # Statistical reference comparisons
        ref_comparisons = []
        for feat_name, feat_val in features.items():
            if feat_val is not None and isinstance(feat_val, (int, float)):
                ref = self.ref_engine.compare(
                    feature_name=feat_name,
                    value=float(feat_val),
                    walking_speed=context.walking_speed_ms,
                )
                if ref.n_reference > 0:
                    ref_comparisons.append(ref)

        # Bilateral assessment
        bilateral_results = []
        if bilateral_features:
            bilateral_results = assess_bilateral_features(
                bilateral_features=bilateral_features,
                side_mapping_verified=False,
            )

        # Overall status
        statuses = [i.status for i in interpretations]
        if n_cycles == 0 or not features or AssessmentStatus.not_assessable in statuses or not interpretations:
            overall = AssessmentStatus.not_assessable
        elif AssessmentStatus.supported in statuses:
            overall = AssessmentStatus.supported
        elif AssessmentStatus.limited_evidence in statuses:
            overall = AssessmentStatus.limited_evidence
        else:
            overall = AssessmentStatus.insufficient_data

        # Merge with uncertainty
        if uncertainty["overall_status"] == AssessmentStatus.not_assessable:
            overall = AssessmentStatus.not_assessable

        global_limitations = [
            "Video-derived estimates only. Not equivalent to laboratory motion capture.",
            "Research dataset reference distributions. Not validated clinical norms.",
            "Anatomical side mapping (left/right) not verified.",
        ]
        if cal_status != "calibrated":
            global_limitations.append(
                "Camera not calibrated \u2014 metric measurements (e.g. speed, stride length) are estimates."
            )

        return GaitAssessment(
            assessment_id=str(uuid.uuid4()),
            context=context,
            overall_status=overall,
            feature_interpretations=interpretations,
            reference_comparisons=ref_comparisons,
            bilateral_results=bilateral_results,
            unsupported_features=[],
            global_limitations=global_limitations,
            created_at=datetime.utcnow(),
        )
