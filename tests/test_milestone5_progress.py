"""Tests for Milestone 5: Progress tracking."""
import pytest
from src.progress.baseline_builder import build_baseline, MIN_SESSIONS_FOR_BASELINE
from src.progress.session_comparator import compare_to_baseline, classify_change
from src.progress.progress_schema import ProgressCategory, ComparabilityDecision
from src.progress.comparability_checker import check_comparability
from src.progress.trend_analyzer import compute_trend, analyze_trends


def _session_features(n=3, cadence=110.0):
    return [{"cadence_steps_per_min": cadence + i, "knee_flexion_rom": 58.0 + i} for i in range(n)]


def test_baseline_insufficient_sessions():
    result = build_baseline("S001", [{"cadence": 110.0}], ["ses1"])
    assert result is None


def test_baseline_built():
    sessions = _session_features(3)
    b = build_baseline("S001", sessions, ["s1", "s2", "s3"])
    assert b is not None
    assert b.n_sessions == 3
    assert b.version == 1
    assert "cadence_steps_per_min" in b.feature_means


def test_baseline_version_increments():
    sessions = _session_features(3)
    b1 = build_baseline("S001", sessions, ["s1", "s2", "s3"], previous_version=0)
    b2 = build_baseline("S001", sessions, ["s1", "s2", "s3", "s4"], ["s1", "s2", "s3", "s4"], previous_version=1)
    assert b1.version == 1
    assert b2.version == 2


def test_progress_no_meaningful_change():
    sessions = _session_features(3, cadence=110.0)
    baseline = build_baseline("S001", sessions, ["s1", "s2", "s3"])
    report = compare_to_baseline(
        subject_id="S001",
        current_session_id="s_new",
        current_features={"cadence_steps_per_min": 111.0},
        baseline=baseline,
    )
    cadence_change = next(fc for fc in report.feature_changes if fc.feature_name == "cadence_steps_per_min")
    assert cadence_change.category == ProgressCategory.no_meaningful_change


def test_classify_change_insufficient_without_sd():
    cat = classify_change(5.0, baseline_sd=None, feature_name="x")
    assert cat == ProgressCategory.insufficient_evidence


def test_comparability_different_view():
    dec, note = check_comparability(
        {"camera_view": "front"}, {"camera_view": "side"}
    )
    assert dec == ComparabilityDecision.conditionally_comparable
    assert "view" in note.lower()


def test_comparability_model_version_mismatch():
    dec, note = check_comparability(
        {"pose_model_version": "v9"}, {"pose_model_version": "v8n-pose"}
    )
    assert dec != ComparabilityDecision.comparable


def test_trend_increasing():
    result = compute_trend([50.0, 55.0, 60.0, 65.0])
    assert result is not None
    assert result[0] == "increasing"


def test_trend_insufficient_points():
    result = compute_trend([50.0, 55.0])
    assert result is None


def test_analyze_trends():
    history = [
        {"cadence": 100.0, "knee_rom": 55.0},
        {"cadence": 105.0, "knee_rom": 57.0},
        {"cadence": 110.0, "knee_rom": 59.0},
    ]
    trends = analyze_trends(history)
    assert "cadence" in trends
    assert trends["cadence"] is not None
    assert trends["cadence"][0] == "increasing"
