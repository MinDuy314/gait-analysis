import pytest
from src.assessment.assessment_engine import AssessmentEngine, categorize_gait_feature
from src.assessment.assessment_schema import AssessmentContext, AssessmentStatus, GaitCategory


def test_categorize_gait_feature_domains():
    assert categorize_gait_feature("cadence") == GaitCategory.temporal.value
    assert categorize_gait_feature("stride_time") == GaitCategory.temporal.value
    assert categorize_gait_feature("walking_speed") == GaitCategory.spatial.value
    assert categorize_gait_feature("step_length") == GaitCategory.spatial.value
    assert categorize_gait_feature("knee_flexion_rom") == GaitCategory.kinematic.value
    assert categorize_gait_feature("hip_flexion_rom") == GaitCategory.kinematic.value
    assert categorize_gait_feature("step_time_symmetry") == GaitCategory.symmetry.value
    assert categorize_gait_feature("trunk_lean") == GaitCategory.postural.value


def test_assessment_groups_measurements_and_preserves_backward_compatibility():
    engine = AssessmentEngine()
    ctx = AssessmentContext(
        subject_id="sub-1",
        session_id="sess-1",
        camera_view="side",
        calibration_status="uncalibrated",
    )
    features = {
        "knee_flexion_rom": 58.5,
        "cadence": 108.0,
        "trunk_lean": 6.2,
    }
    confidences = {
        "knee_flexion_rom": 0.9,
        "cadence": 0.85,
        "trunk_lean": 0.8,
    }
    assessment = engine.assess(
        context=ctx,
        features=features,
        confidences=confidences,
        n_cycles=4,
        event_confidence=0.85,
        cycle_quality=0.85,
    )
    # Backward-compatible flat list still populated
    assert len(assessment.feature_interpretations) >= 1
    # Grouped measurements has all 5 domain keys
    for cat in GaitCategory:
        assert cat.value in assessment.grouped_measurements
    # Knee flexion ROM is grouped under kinematic
    kinematic_names = [f.feature_name for f in assessment.grouped_measurements["kinematic"]]
    assert "knee_flexion_rom" in kinematic_names
    # No fabricated spatial values when uncalibrated
    for f in assessment.grouped_measurements["spatial"]:
        assert f.value is None
        assert f.status == AssessmentStatus.not_assessable
