from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from src.assessment.assessment_schema import (
    AssessmentStatus, FeatureInterpretation, UncertaintySource
)


@dataclass
class BiomechanicalRule:
    name: str
    required_features: List[str]
    required_camera_views: List[str]  # empty = any view
    min_confidence: float
    description: str
    evidence_source: str
    limitations: List[str]
    _interpret_fn: Callable  # set via method

    def evaluate(
        self,
        features: Dict[str, Any],
        camera_view: str,
        confidences: Dict[str, float],
    ) -> Optional[FeatureInterpretation]:
        # Check view requirement
        if self.required_camera_views and camera_view not in self.required_camera_views:
            return None
        # Check all required features present with sufficient confidence
        for feat in self.required_features:
            if features.get(feat) is None:
                return FeatureInterpretation(
                    feature_name=feat,
                    status=AssessmentStatus.insufficient_data,
                    interpretation_text=f"Feature '{feat}' not available.",
                    limitations=self.limitations,
                )
            if confidences.get(feat, 0.0) < self.min_confidence:
                return FeatureInterpretation(
                    feature_name=feat,
                    status=AssessmentStatus.limited_evidence,
                    interpretation_text=f"Feature '{feat}' confidence below threshold ({self.min_confidence}).",
                    limitations=self.limitations,
                )
        return self._interpret_fn(features, confidences)


def build_default_rules() -> List[BiomechanicalRule]:
    rules = []

    def _knee_flexion(features, confidences):
        rom = features.get("knee_flexion_rom")
        conf = confidences.get("knee_flexion_rom", 0.0)
        if rom is None:
            return None
        if rom < 30:
            text = (
                f"Knee flexion range ({rom:.1f}\u00b0) is below the lower boundary of the research "
                f"dataset distribution (< 30\u00b0). This observation requires clinical interpretation."
            )
        elif rom > 100:
            text = (
                f"Knee flexion range ({rom:.1f}\u00b0) is above the upper boundary of the research "
                f"dataset distribution (> 100\u00b0). This observation requires clinical interpretation."
            )
        else:
            text = (
                f"Knee flexion range ({rom:.1f}\u00b0) is within the research dataset distribution "
                f"(30\u2013100\u00b0). This is a research reference range, not a clinical norm."
            )
        return FeatureInterpretation(
            feature_name="knee_flexion_rom",
            value=rom,
            unit="degrees",
            status=AssessmentStatus.supported,
            rule_name="knee_flexion_range",
            interpretation_text=text,
            evidence_sources=["video_pose_estimation", "research_dataset_distribution"],
            confidence=conf,
            limitations=[
                "Research dataset distribution only. Not a validated clinical norm.",
                "Video-derived estimate, not motion-capture.",
            ],
            uncertainty_sources=[
                UncertaintySource(
                    source="pose_estimation",
                    description="2D projection uncertainty",
                    severity="medium",
                )
            ],
        )

    r1 = BiomechanicalRule(
        name="knee_flexion_range",
        required_features=["knee_flexion_rom"],
        required_camera_views=["side"],
        min_confidence=0.4,
        description="Knee flexion range of motion assessment against research distribution",
        evidence_source="research_dataset_distribution",
        limitations=["Research dataset distribution only. Not a validated clinical norm."],
        _interpret_fn=_knee_flexion,
    )
    rules.append(r1)

    def _cadence(features, confidences):
        cad = features.get("cadence_steps_per_min")
        conf = confidences.get("cadence_steps_per_min", 0.9)
        if cad is None:
            return None
        if cad < 80:
            text = (
                f"Cadence ({cad:.1f} steps/min) is below 80 steps/min, which is below the typical "
                f"adult walking range in this research dataset."
            )
        elif cad > 140:
            text = (
                f"Cadence ({cad:.1f} steps/min) is above 140 steps/min, which is above the typical "
                f"range in this research dataset."
            )
        else:
            text = (
                f"Cadence ({cad:.1f} steps/min) is within the typical range in this research dataset "
                f"(80\u2013140 steps/min)."
            )
        return FeatureInterpretation(
            feature_name="cadence_steps_per_min",
            value=cad,
            unit="steps/min",
            status=AssessmentStatus.supported,
            rule_name="cadence_assessment",
            interpretation_text=text,
            evidence_sources=["video_temporal_analysis"],
            confidence=conf,
            limitations=["Research dataset reference range only."],
        )

    r2 = BiomechanicalRule(
        name="cadence_assessment",
        required_features=["cadence_steps_per_min"],
        required_camera_views=[],  # any view
        min_confidence=0.5,
        description="Cadence assessment against research dataset distribution",
        evidence_source="video_temporal_analysis",
        limitations=["Research dataset reference range only."],
        _interpret_fn=_cadence,
    )
    rules.append(r2)

    def _hip_flexion(features, confidences):
        rom = features.get("hip_flexion_rom")
        conf = confidences.get("hip_flexion_rom", 0.0)
        if rom is None:
            return None
        text = f"Hip flexion range ({rom:.1f}\u00b0) recorded from video estimation."
        return FeatureInterpretation(
            feature_name="hip_flexion_rom",
            value=rom,
            unit="degrees",
            status=AssessmentStatus.limited_evidence,
            rule_name="hip_flexion_range",
            interpretation_text=text,
            evidence_sources=["video_pose_estimation"],
            confidence=conf,
            limitations=[
                "Hip angle estimated from 2D projection. 3D motion capture reference required for clinical interpretation."
            ],
        )

    r3 = BiomechanicalRule(
        name="hip_flexion_range",
        required_features=["hip_flexion_rom"],
        required_camera_views=["side"],
        min_confidence=0.3,
        description="Hip flexion range of motion — limited evidence from video",
        evidence_source="video_pose_estimation",
        limitations=["2D video projection. Not equivalent to 3D motion capture."],
        _interpret_fn=_hip_flexion,
    )
    rules.append(r3)

    def _stride_time_variability(features, confidences):
        sd = features.get("stride_time_sd")
        conf = confidences.get("stride_time_sd", 0.5)
        if sd is None:
            return None
        if sd < 0.02:
            text = f"Stride time variability (SD={sd:.3f}s) is very low, indicating highly regular gait in this recording."
        elif sd > 0.1:
            text = (
                f"Stride time variability (SD={sd:.3f}s) is elevated. High variability may reflect "
                f"irregular terrain, measurement noise, or true gait irregularity. Clinical interpretation required."
            )
        else:
            text = f"Stride time variability (SD={sd:.3f}s) is within a typical range for this research dataset."
        return FeatureInterpretation(
            feature_name="stride_time_sd",
            value=sd,
            unit="seconds",
            status=AssessmentStatus.supported,
            rule_name="stride_time_variability",
            interpretation_text=text,
            evidence_sources=["video_temporal_analysis"],
            confidence=conf,
            limitations=["Research dataset reference range only. Not a clinical norm."],
        )

    r4 = BiomechanicalRule(
        name="stride_time_variability",
        required_features=["stride_time_sd"],
        required_camera_views=[],  # any view
        min_confidence=0.4,
        description="Stride time variability assessment",
        evidence_source="video_temporal_analysis",
        limitations=["Research dataset reference range only."],
        _interpret_fn=_stride_time_variability,
    )
    rules.append(r4)

    return rules
