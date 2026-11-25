from typing import Any, Dict, List, Optional
from src.assessment.assessment_schema import AssessmentStatus, UncertaintySource


def aggregate_uncertainty(
    landmark_confidence: float,
    feature_confidence: float,
    event_confidence: float,
    cycle_quality: float,
    n_cycles: int,
    camera_view: str,
    calibration_status: str,
) -> Dict[str, Any]:
    sources: List[UncertaintySource] = []

    if landmark_confidence < 0.5:
        sources.append(
            UncertaintySource(source="landmark_detection", description=f"Low landmark confidence: {landmark_confidence:.2f}", severity="high")
        )
    if feature_confidence < 0.5:
        sources.append(
            UncertaintySource(source="feature_extraction", description=f"Low feature confidence: {feature_confidence:.2f}", severity="high")
        )
    if event_confidence < 0.5:
        sources.append(
            UncertaintySource(source="event_detection", description=f"Low gait event confidence: {event_confidence:.2f}", severity="medium")
        )
    if cycle_quality < 0.5:
        sources.append(
            UncertaintySource(source="cycle_segmentation", description=f"Low cycle quality: {cycle_quality:.2f}", severity="medium")
        )
    if n_cycles < 3:
        sources.append(
            UncertaintySource(source="sample_size", description=f"Only {n_cycles} complete cycles \u2014 mean estimates may be unreliable.", severity="medium" if n_cycles > 0 else "high")
        )
    if camera_view not in ("side", "front", "rear"):
        sources.append(
            UncertaintySource(source="camera_view", description=f"Unsupported camera view: {camera_view}", severity="high")
        )
    if calibration_status != "calibrated":
        sources.append(
            UncertaintySource(source="calibration", description="Camera not calibrated \u2014 metric measurements are estimates.", severity="medium")
        )

    overall_min = min(landmark_confidence, feature_confidence, event_confidence, cycle_quality)

    if n_cycles == 0:
        status = AssessmentStatus.not_assessable
    elif overall_min >= 0.7 and n_cycles >= 3:
        status = AssessmentStatus.supported
    elif overall_min >= 0.4 and n_cycles >= 1:
        status = AssessmentStatus.limited_evidence
    else:
        status = AssessmentStatus.insufficient_data

    return {
        "overall_status": status,
        "uncertainty_sources": sources,
        "overall_confidence": float(overall_min),
    }
