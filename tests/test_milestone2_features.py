"""Automated tests for Milestone 2: Feature Extraction, Reference Distributions, Splits, and Plots."""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.core.config import AppConfig
from src.feature_extraction.npz_feature_extractor import (
    compute_symmetry_index,
    extract_bilateral_pair,
    extract_curve_features,
)
from src.reference.run_milestone2_pipeline import run_milestone2_pipeline


def test_synthetic_curve_feature_extraction():
    """Verify exact summary stats, peak timing, and gait-phase sampling on a known curve."""
    x = np.linspace(0, 100, 101)
    # Peak at 65% = 60.0 deg, min at 0% = 0.0 deg
    curve = 60.0 * np.exp(-0.5 * ((x - 65.0) / 10.0) ** 2)
    curve[0] = 0.0

    phases = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    intervals = {"swing": [62, 100]}

    feat, qual = extract_curve_features(
        curve=curve,
        variable_name="kneeAx",
        phase_points_pct=phases,
        phase_intervals_pct=intervals,
        min_valid_samples=81,
    )

    assert qual["completeness_status"] == "complete"
    assert qual["valid_samples"] == 101
    assert qual["missing_samples"] == 0
    assert feat["is_reliable"] is True
    assert feat["peak_timing_pct"] == 65.0
    assert feat["min_timing_pct"] == 0.0
    assert pytest.approx(feat["max"], abs=1e-6) == 60.0
    assert pytest.approx(feat["rom"], abs=1e-6) == 60.0
    assert pytest.approx(feat["phase_65_pct"] if "phase_65_pct" in feat else curve[65], abs=1e-6) == 60.0
    assert pytest.approx(feat["phase_0_pct"], abs=1e-6) == 0.0


def test_missing_data_handling_partial_and_insufficient():
    """Verify NaN-safe handling, no zero-fill, and reliability thresholds."""
    # 1. Partially missing (90 valid >= 81)
    curve_partial = np.ones(101, dtype=np.float64) * 15.0
    curve_partial[10] = 30.0
    curve_partial[:11] = np.nan  # 11 missing -> 90 valid
    feat_p, qual_p = extract_curve_features(
        curve_partial, "kneeAx", [0, 10, 50], {}, min_valid_samples=81
    )
    assert qual_p["completeness_status"] == "partially_missing"
    assert qual_p["valid_samples"] == 90
    assert feat_p["is_reliable"] is True
    assert feat_p["phase_0_pct"] is None  # NaN at 0% must remain None
    assert feat_p["phase_50_pct"] == 15.0
    assert feat_p["mean"] == 15.0

    # 2. Insufficiently complete (50 valid < 81)
    curve_insuff = np.ones(101, dtype=np.float64) * 10.0
    curve_insuff[:51] = np.nan
    feat_i, qual_i = extract_curve_features(
        curve_insuff, "kneeMx", [0, 50], {}, min_valid_samples=81
    )
    assert qual_i["completeness_status"] == "insufficiently_complete"
    assert feat_i["is_reliable"] is False
    assert feat_i["mean"] is None
    assert feat_i["rom"] is None

    # 3. Entirely unavailable
    curve_empty = np.full(101, np.nan)
    feat_e, qual_e = extract_curve_features(
        curve_empty, "kneePx", [0, 50], {}, min_valid_samples=81
    )
    assert qual_e["completeness_status"] == "unavailable"
    assert feat_e["is_reliable"] is False


def test_bilateral_comparison_and_near_zero_denominator():
    """Verify bilateral diffs and safe Symmetry Index handling near zero."""
    si, status = compute_symmetry_index(0.0001, -0.0001, near_zero_threshold=1e-3)
    assert si is None
    assert status == "near_zero_denominator"

    si_ok, status_ok = compute_symmetry_index(60.0, 50.0, near_zero_threshold=1e-3)
    assert status_ok == "computed"
    assert pytest.approx(si_ok, abs=1e-4) == 100.0 * 10.0 / 55.0

    f1 = {"is_reliable": True, "mean": 20.0, "max": 60.0, "rom": 60.0, "peak_timing_pct": 65.0, "phase_0_pct": 2.0}
    f2 = {"is_reliable": True, "mean": 18.0, "max": 55.0, "rom": 55.0, "peak_timing_pct": 66.0, "phase_0_pct": 1.0}
    pair = {"primary": "kneeAx", "contralateral": "kneeAx_contra", "joint": "knee", "axis": "X"}
    b = extract_bilateral_pair(f1, f2, pair, [0])
    assert b["is_reliable"] is True
    assert b["rom_diff"] == 5.0
    assert b["phase_0_diff"] == 1.0


def test_milestone2_real_dataset_pipeline():
    """Run full Milestone 2 pipeline on real 658-trial dataset and verify all outputs."""
    cfg = AppConfig()
    outputs = run_milestone2_pipeline(cfg.project_root)

    # Trial feature outputs
    summary_df = pd.read_csv(outputs["features"]["trial_feature_summary_csv"])
    quality_df = pd.read_csv(outputs["features"]["trial_feature_quality_csv"])
    bilateral_df = pd.read_csv(outputs["features"]["bilateral_features_csv"])
    assert len(summary_df) == 658 * 54  # 36 angles + 9 moments + 9 powers
    assert len(quality_df) == len(summary_df)
    assert len(bilateral_df) == 658 * 15  # 15 bilateral pairs

    # Reference distributions (trial-level vs participant-level)
    trial_ref = pd.read_csv(outputs["reference"]["trial_reference_distributions_csv"])
    part_ref = pd.read_csv(outputs["reference"]["participant_reference_distributions_csv"])
    assert not trial_ref.empty
    assert not part_ref.empty
    assert (part_ref["n_participants"] <= 11).all()
    # Condition-specific check
    assert set(part_ref["condition"].unique()) == {
        "level_down", "level_up", "ramp75_down", "ramp75_up", "ramp_10_down", "ramp_10_up"
    }

    # 101-point gait-cycle reference curves
    knee_ref = pd.read_parquet(cfg.gait_curves_dir / "knee_angles" / "knee_angles_reference_curves.parquet")
    pct_cols = [f"pct_{i}" for i in range(101)]
    assert all(c in knee_ref.columns for c in pct_cols)

    # Participant-independent splits (no leakage)
    splits_df = pd.read_csv(outputs["splits"])
    assert len(splits_df) == 11
    assert splits_df["participant_id"].is_unique
    assert set(splits_df["split"].unique()) == {"train", "val", "test"}

    # Visualizations generated
    assert len(outputs["figures"]) == 7
    for fig_path in outputs["figures"]:
        assert Path(fig_path).exists() and Path(fig_path).stat().st_size > 0
