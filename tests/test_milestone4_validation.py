"""Automated test suite for Milestone 4: Biomechanical Validation."""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.core.config import AppConfig
from src.validation.agreement_metrics import calculate_agreement_metrics
from src.validation.curve_validation import validate_gait_curves
from src.validation.event_validation import evaluate_gait_events
from src.validation.feature_mapping import (
    COMPATIBILITY_DEFINITIONS,
    export_compatibility_matrix,
    get_compatibility_definition,
)
from src.validation.validation_runner import run_biomechanical_validation


def test_feature_compatibility_rules():
    """Verify explicit compatibility statuses and rejection of mismatched units/planes."""
    knee_def = get_compatibility_definition("left_knee_flexion_extension_rom")
    assert knee_def is not None
    assert knee_def.compatibility_status == "conditionally_comparable"
    assert knee_def.movement_plane == "sagittal"
    assert knee_def.units_compatible is True

    cadence_def = get_compatibility_definition("cadence")
    assert cadence_def is not None
    assert cadence_def.compatibility_status == "not_comparable"
    assert cadence_def.units_compatible is False

    trunk_def = get_compatibility_definition("trunk_lateral_displacement_px")
    assert trunk_def is not None
    assert trunk_def.compatibility_status == "not_comparable"
    assert trunk_def.video_units == "pixels"
    assert trunk_def.reference_units == "degrees"


def test_gait_event_matching_and_timing_metrics():
    """Verify event evaluation, precision, recall, F1, and signed timing error in ms."""
    ref_events = [1.0, 2.0, 3.0, 4.0]
    # Det events:
    # 1.05 (error +50ms), 2.02 (error +20ms), 3.08 (error +80ms), 5.50 (false positive)
    # 4.0 is missed (false negative)
    det_events = [1.05, 2.02, 3.08, 5.50]

    metrics = evaluate_gait_events(
        detected_events_s=det_events,
        reference_events_s=ref_events,
        tolerance_ms=100.0,
    )

    assert metrics.total_reference_events == 4
    assert metrics.total_detected_events == 4
    assert metrics.true_positives == 3
    assert metrics.false_positives == 1
    assert metrics.false_negatives == 1
    assert pytest.approx(metrics.precision, abs=1e-3) == 0.75
    assert pytest.approx(metrics.recall, abs=1e-3) == 0.75
    assert pytest.approx(metrics.f1_score, abs=1e-3) == 0.75
    assert pytest.approx(metrics.timing_mae_ms, abs=1e-2) == 50.0  # (|50| + |20| + |80|) / 3


def test_agreement_metrics_bland_altman_and_bootstrap():
    """Verify bias, MAE, RMSE, Bland-Altman LoA, and bootstrap CI with known differences."""
    ref = np.array([10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
    # Constant bias +2.0 deg
    vid = ref + 2.0
    participants = ["P1", "P1", "P2", "P2", "P3", "P3"]

    ag = calculate_agreement_metrics(
        video_vals=vid,
        ref_vals=ref,
        feature_name="knee_rom",
        participant_ids=participants,
        n_bootstrap=200,
    )

    assert ag.n_observations == 6
    assert ag.n_participants == 3
    assert pytest.approx(ag.mean_bias, abs=1e-4) == 2.0
    assert pytest.approx(ag.mae, abs=1e-4) == 2.0
    assert pytest.approx(ag.rmse, abs=1e-4) == 2.0
    assert pytest.approx(ag.pearson_r, abs=1e-4) == 1.0
    assert pytest.approx(ag.bland_altman_sd, abs=1e-4) == 0.0
    assert pytest.approx(ag.bland_altman_lower_loa, abs=1e-4) == 2.0
    assert pytest.approx(ag.bland_altman_upper_loa, abs=1e-4) == 2.0
    assert pytest.approx(ag.bootstrap_mae_ci_lower, abs=1e-4) == 2.0
    assert pytest.approx(ag.bootstrap_mae_ci_upper, abs=1e-4) == 2.0


def test_gait_curve_pointwise_comparison_with_nans():
    """Verify pointwise MAE/bias curve calculations with preserved NaNs."""
    c_ref = np.zeros(101, dtype=np.float64)
    c_vid = np.ones(101, dtype=np.float64) * 3.0
    c_vid[50] = np.nan  # NaN preserved

    summary = validate_gait_curves(
        video_curves=[c_vid],
        ref_curves=[c_ref],
        feature_name="knee_curve",
        reference_var="kneeAx",
    )

    assert summary.n_paired_cycles == 1
    assert pytest.approx(summary.mean_curve_mae, abs=1e-3) == 3.0
    assert summary.pointwise_mae_curve[0] == 3.0
    assert summary.pointwise_mae_curve[50] is None  # preserved NaN


def test_validation_runner_and_artifacts():
    """Run Milestone 4 validation pipeline and check all generated artifacts."""
    cfg = AppConfig()
    artifacts = run_biomechanical_validation(cfg)

    for key, path in artifacts.items():
        assert Path(path).exists()
        assert Path(path).stat().st_size > 0

    # Verify report is generated with correct scientific transparency
    report_text = Path(artifacts["report_markdown"]).read_text(encoding="utf-8")
    assert "Feature Compatibility Matrix" in report_text
    assert "not_testable" in report_text
    assert "Conditionally Comparable" in report_text
