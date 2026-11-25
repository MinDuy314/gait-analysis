"""Automated tests for Milestone 1: NPZ Discovery, Schema Validation, Metadata, and QC."""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.core.config import AppConfig
from src.data_loader.npz_discovery import discover_npz_dataset
from src.data_loader.npz_validator import (
    EXPECTED_VARIABLES,
    CURVE_101_VARS,
    VECTOR_2_VARS,
    METADATA_SCALARS,
    OTHER_SCALARS,
    validate_all_npz,
    validate_npz_trial,
)
from src.data_loader.run_npz_pipeline import run_milestone1_pipeline


def _create_synthetic_npz(path: Path, overrides: dict = None, omit_keys: set = None) -> None:
    """Helper to create a valid or intentionally malformed synthetic NPZ file."""
    payload = {}
    for k in EXPECTED_VARIABLES:
        if omit_keys and k in omit_keys:
            continue
        if k == "prob":
            payload[k] = np.array("Ref99")
        elif k == "folder":
            payload[k] = np.array("level_up")
        elif k == "gait_speed":
            payload[k] = np.array(1.25, dtype=np.float64)
        elif k in OTHER_SCALARS:
            payload[k] = np.array(0.95, dtype=np.float64)
        elif k in VECTOR_2_VARS:
            payload[k] = np.zeros((2,), dtype=np.float64)
        elif k in CURVE_101_VARS:
            payload[k] = np.zeros((101,), dtype=np.float64)

    if overrides:
        payload.update(overrides)
    np.savez(path, **payload)


def test_real_dataset_discovery_and_pipeline():
    """Verify all 658 NPZ trials are discovered, validated, and indexed without modifying raw data."""
    cfg = AppConfig()
    discovery_report, validation_report = run_milestone1_pipeline(cfg.project_root)

    assert discovery_report.total_files_discovered == 658
    assert len(discovery_report.participants_found) == 11
    assert set(discovery_report.missing_expected_participants) == {"Ref03", "Ref04"}
    assert len(discovery_report.duplicate_content_hashes) == 0
    assert len(discovery_report.duplicate_filenames) == 12  # Same filename across up/down folders

    assert validation_report.total_files_discovered == 658
    assert validation_report.invalid_files == 0
    assert validation_report.total_shape_inconsistencies == 0
    assert validation_report.total_missing_variables_events == 0

    # Verify generated metadata & QC files
    trial_df = pd.read_csv(cfg.metadata_dir / "trial_index.csv")
    subject_df = pd.read_csv(cfg.metadata_dir / "subject_index.csv")
    var_df = pd.read_csv(cfg.metadata_dir / "variable_dictionary.csv")
    qc_summary_df = pd.read_csv(cfg.qc_dir / "qc_summary.csv")
    missing_df = pd.read_csv(cfg.qc_dir / "missing_data.csv")
    invalid_df = pd.read_csv(cfg.qc_dir / "invalid_trials.csv")

    assert len(trial_df) == 658
    assert trial_df["trial_id"].is_unique
    assert len(subject_df) == 13  # Ref01..Ref13
    assert len(var_df) == 79
    assert len(qc_summary_df) > 0
    assert len(missing_df) == validation_report.total_numeric_anomaly_records
    assert len(invalid_df) >= 0


def test_synthetic_valid_and_malformed_npz(tmp_path: Path):
    """Verify schema validator catches missing vars, wrong shapes, NaNs, and Infs."""
    npz_root = tmp_path / "npz"
    trial_dir = npz_root / "Ref99" / "level_up"
    trial_dir.mkdir(parents=True)

    valid_file = trial_dir / "Ref99_valid.npz"
    _create_synthetic_npz(valid_file)

    missing_knee_file = trial_dir / "Ref99_missing_knee.npz"
    _create_synthetic_npz(missing_knee_file, omit_keys={"kneeAx"})

    bad_shape_file = trial_dir / "Ref99_bad_shape.npz"
    _create_synthetic_npz(bad_shape_file, overrides={"kneeAx": np.zeros((50,), dtype=np.float64)})

    nan_inf_file = trial_dir / "Ref99_nan_inf.npz"
    bad_curve = np.zeros((101,), dtype=np.float64)
    bad_curve[0] = np.nan
    bad_curve[1] = np.inf
    _create_synthetic_npz(nan_inf_file, overrides={"kneeMx": bad_curve})

    disc = discover_npz_dataset(npz_root, project_root=tmp_path)
    assert disc.total_files_discovered == 4

    report = validate_all_npz(disc.files)
    by_id = {r.trial_id: r for r in report.trial_results}

    assert by_id["level_up__Ref99_valid"].validation_status == "valid"
    assert by_id["level_up__Ref99_missing_knee"].validation_status == "invalid"
    assert "kneeAx" in by_id["level_up__Ref99_missing_knee"].missing_knee_variables
    assert by_id["level_up__Ref99_bad_shape"].validation_status == "invalid"
    assert len(by_id["level_up__Ref99_bad_shape"].shape_inconsistencies) == 1
    assert by_id["level_up__Ref99_nan_inf"].validation_status == "valid_with_numeric_anomalies"
    assert by_id["level_up__Ref99_nan_inf"].has_kinetic_anomalies is True
    assert by_id["level_up__Ref99_nan_inf"].numeric_anomalies[0].anomaly_type == "nan_and_inf"
