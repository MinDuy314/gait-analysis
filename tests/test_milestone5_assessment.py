"""Tests for Milestone 5: Assessment engine."""
import pytest
from src.assessment.assessment_schema import AssessmentContext, AssessmentStatus
from src.assessment.assessment_engine import AssessmentEngine
from src.assessment.biomechanical_rules import build_default_rules
from src.assessment.bilateral_assessment import assess_bilateral_features
from src.assessment.uncertainty_propagation import aggregate_uncertainty


def _ctx(**kw):
    return AssessmentContext(subject_id="S001", session_id="SES001", **kw)


def test_knee_flexion_rule_supported():
    rules = build_default_rules()
    knee_rule = next(r for r in rules if r.name == "knee_flexion_range")
    result = knee_rule.evaluate(
        features={"knee_flexion_rom": 58.0},
        camera_view="side",
        confidences={"knee_flexion_rom": 0.75},
    )
    assert result is not None
    assert result.status == AssessmentStatus.supported


def test_knee_flexion_rule_wrong_view():
    rules = build_default_rules()
    knee_rule = next(r for r in rules if r.name == "knee_flexion_range")
    result = knee_rule.evaluate(
        features={"knee_flexion_rom": 58.0},
        camera_view="front",
        confidences={"knee_flexion_rom": 0.75},
    )
    assert result is None


def test_knee_flexion_rule_low_confidence():
    rules = build_default_rules()
    knee_rule = next(r for r in rules if r.name == "knee_flexion_range")
    result = knee_rule.evaluate(
        features={"knee_flexion_rom": 58.0},
        camera_view="side",
        confidences={"knee_flexion_rom": 0.1},
    )
    assert result.status == AssessmentStatus.limited_evidence


def test_knee_flexion_missing_feature():
    rules = build_default_rules()
    knee_rule = next(r for r in rules if r.name == "knee_flexion_range")
    result = knee_rule.evaluate(features={}, camera_view="side", confidences={})
    assert result.status == AssessmentStatus.insufficient_data


def test_assessment_engine_with_features():
    engine = AssessmentEngine()
    ctx = _ctx(camera_view="side", calibration_status="uncalibrated")
    assessment = engine.assess(
        context=ctx,
        features={"knee_flexion_rom": 58.0, "cadence_steps_per_min": 110.0},
        confidences={"knee_flexion_rom": 0.75, "cadence_steps_per_min": 0.9},
        n_cycles=5,
    )
    assert assessment.overall_status in list(AssessmentStatus)
    assert len(assessment.feature_interpretations) > 0
    assert len(assessment.global_limitations) > 0


def test_assessment_engine_no_features():
    engine = AssessmentEngine()
    ctx = _ctx(camera_view="side")
    assessment = engine.assess(context=ctx, features={}, n_cycles=0)
    assert assessment.overall_status == AssessmentStatus.not_assessable


def test_bilateral_assessment_no_mapping():
    results = assess_bilateral_features(
        {"stride_time": 1.1, "stride_time_contra": 1.0},
        side_mapping_verified=False,
    )
    assert len(results) == 1
    r = results[0]
    assert r.absolute_difference is not None
    assert not r.side_mapping_verified
    assert any("not verified" in lim for lim in r.limitations)


def test_bilateral_assessment_missing_side():
    results = assess_bilateral_features({"step_length": None, "step_length_contra": 0.6})
    assert results[0].absolute_difference is None


def test_uncertainty_not_assessable():
    u = aggregate_uncertainty(
        landmark_confidence=0.1, feature_confidence=0.1,
        event_confidence=0.1, cycle_quality=0.1,
        n_cycles=0, camera_view="unknown", calibration_status="uncalibrated",
    )
    assert u["overall_status"] == AssessmentStatus.not_assessable


def test_uncertainty_supported():
    u = aggregate_uncertainty(
        landmark_confidence=0.9, feature_confidence=0.9,
        event_confidence=0.8, cycle_quality=0.85,
        n_cycles=5, camera_view="side", calibration_status="calibrated",
    )
    assert u["overall_status"] == AssessmentStatus.supported
