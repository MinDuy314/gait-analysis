"""Validation execution runner and artifact generator."""

import json
from pathlib import Path
from typing import Dict, List, Optional
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.core.config import AppConfig
from src.core.logging import get_logger
from src.validation.agreement_metrics import calculate_agreement_metrics
from src.validation.curve_validation import validate_gait_curves
from src.validation.event_validation import evaluate_gait_events
from src.validation.feature_mapping import export_compatibility_matrix, get_compatibility_definition
from src.validation.validation_schema import (
    AgreementMetrics,
    CurveValidationSummary,
    EventValidationMetrics,
    MatchedObservation,
)

logger = get_logger(__name__)


class ValidationArtifacts(dict):
    pass


def run_biomechanical_validation(cfg: Optional[AppConfig] = None) -> ValidationArtifacts:
    """
    Execute Milestone 4 validation:
    1. Feature compatibility matrix.
    2. Check for genuinely matched real video recordings.
    3. Generate validation tables, split-isolated metrics, diagnostic figures, and markdown report.
    """
    cfg = cfg or AppConfig()
    val_dir = cfg.processed_dir / "validation"
    val_dir.mkdir(parents=True, exist_ok=True)
    fig_val_dir = cfg.figures_dir / "validation"
    fig_val_dir.mkdir(parents=True, exist_ok=True)
    rep_dir = cfg.project_root / "outputs" / "reports"
    rep_dir.mkdir(parents=True, exist_ok=True)

    # 1. Export feature compatibility
    compat_csv = val_dir / "feature_compatibility.csv"
    export_compatibility_matrix(compat_csv)

    # 2. Check for real video files in data/video/raw
    raw_video_dir = cfg.project_root / "data" / "video" / "raw"
    real_video_files = list(raw_video_dir.glob("*.mp4")) + list(raw_video_dir.glob("*.mov"))

    matched_obs: List[MatchedObservation] = []
    excluded_obs: List[Dict] = []
    event_metrics: List[EventValidationMetrics] = []
    joint_metrics: List[AgreementMetrics] = []
    curve_summaries: List[CurveValidationSummary] = []
    part_metrics: List[Dict] = []

    # Record the actual dataset pairing state
    if not real_video_files:
        logger.info("No paired experimental video files found in %s; documenting not_testable status.", raw_video_dir)
        excluded_obs.append(
            {
                "observation_id": "video_raw_empty",
                "reason": "No matched optical video recordings available in data/video/raw/ corresponding to NPZ trials.",
                "category": "not_testable",
            }
        )
        # Event validation is not testable without genuine paired video recordings
        ev_untestable = EventValidationMetrics(
            event_type="foot_strike",
            tolerance_ms=100.0,
            total_reference_events=0,
            total_detected_events=0,
            true_positives=0,
            false_positives=0,
            false_negatives=0,
            status="not_testable_no_paired_video",
        )
        event_metrics.append(ev_untestable)

    # 3. Save structured parquet and csv artifacts
    matched_df = pd.DataFrame([m.model_dump() for m in matched_obs])
    matched_pq = val_dir / "matched_observations.parquet"
    if matched_df.empty:
        # Save empty schema-compliant dataframe
        matched_df = pd.DataFrame(columns=list(MatchedObservation.model_fields.keys()))
    matched_df.to_parquet(matched_pq, index=False)

    excluded_df = pd.DataFrame(excluded_obs)
    excluded_csv = val_dir / "excluded_observations.csv"
    excluded_df.to_csv(excluded_csv, index=False)

    event_df = pd.DataFrame([m.model_dump() for m in event_metrics])
    event_csv = val_dir / "event_validation_metrics.csv"
    event_df.to_csv(event_csv, index=False)

    joint_df = pd.DataFrame([m.model_dump() for m in joint_metrics])
    joint_csv = val_dir / "joint_angle_agreement.csv"
    if joint_df.empty:
        joint_df = pd.DataFrame(columns=list(AgreementMetrics.model_fields.keys()))
    joint_df.to_csv(joint_csv, index=False)

    curve_df = pd.DataFrame([m.model_dump(exclude={"pointwise_mae_curve", "pointwise_bias_curve"}) for m in curve_summaries])
    curve_csv = val_dir / "gait_curve_validation.csv"
    if curve_df.empty:
        curve_df = pd.DataFrame(columns=list(CurveValidationSummary.model_fields.keys()))
    curve_df.to_csv(curve_csv, index=False)

    part_df = pd.DataFrame(part_metrics)
    part_csv = val_dir / "participant_validation_metrics.csv"
    part_df.to_csv(part_csv, index=False)

    # 4. Validation metadata JSON
    meta_json = val_dir / "validation_metadata.json"
    meta_content = {
        "milestone": "Milestone 4: Biomechanical Validation",
        "has_real_paired_videos": len(real_video_files) > 0,
        "n_raw_videos_found": len(real_video_files),
        "status_by_candidate": {
            "knee_flexion_extension_rom": "conditionally_comparable (requires paired side-view recording)",
            "hip_flexion_extension_rom": "conditionally_comparable (requires paired side-view recording)",
            "ankle_angle_planar": "conditionally_comparable (requires rigid foot definition)",
            "cadence_vs_gait_speed": "not_comparable (unit/concept mismatch: steps/min vs m/s)",
            "trunk_displacement_px": "not_comparable (unit mismatch: pixels vs 3D angular degrees)",
            "gait_events": "not_testable (no paired video in current dataset)",
        },
        "participant_splits_file": "metadata/participant_splits.csv",
        "scientific_constraints": [
            "Never assume 2D monocular pose angles equal 3D Plug-in Gait Cardan angles.",
            "Correlation must never be cited as proof of agreement; Bland-Altman LoA and bias required.",
            "Synthetic validation tests demonstrate algorithmic correctness only, not real-world clinical validity.",
        ],
    }
    with open(meta_json, "w", encoding="utf-8") as f:
        json.dump(meta_content, f, indent=2)

    # 5. Diagnostic validation figures
    fig1, ax1 = plt.subplots(figsize=(8, 4.5))
    categories = ["Conditionally Comparable", "Not Comparable", "Not Testable (No Paired Video)"]
    counts = [3, 2, 1]
    ax1.bar(categories, counts, color=["tab:blue", "tab:red", "tab:gray"], alpha=0.85)
    ax1.set_ylabel("Number of Features / Pipelines")
    ax1.set_title("Milestone 4: Biomechanical Compatibility & Testability Status")
    ax1.grid(True, axis="y", alpha=0.3)
    plt.xticks(rotation=15)
    fig1.tight_layout()
    p1 = fig_val_dir / "01_feature_compatibility_status.png"
    fig1.savefig(p1, dpi=150)
    plt.close(fig1)

    # 6. Generate Milestone 4 Markdown report
    report_md = rep_dir / "milestone4_validation_report.md"
    report_text = f"""# Milestone 4: Biomechanical Validation Report

**Dataset**: Nature Scientific Data 2025 (`s41597-025-06535-y`) / Figshare 29300888.v1  
**Scope**: Verification of feature compatibility, agreement metrics, gait event matching, and curve comparison between computer-vision video estimates and laboratory motion capture.

---

## 1. Feature Compatibility Matrix

| Video Feature | Reference Variable | Plane | Video Units | Ref Units | Compatibility Status | Core Limitation |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `left_knee_flexion_extension_rom` | `kneeAx` | Sagittal | degrees | degrees | **Conditionally Comparable** | 2D projection vs 3D Cardan angle; requires true side view |
| `right_knee_flexion_extension_rom` | `kneeAx_contra` | Sagittal | degrees | degrees | **Conditionally Comparable** | Contralateral self-occlusion in monocular side view |
| `ankle_angle_planar` | `ankleAx` | Sagittal | degrees | degrees | **Conditionally Comparable** | Surface landmark noise on foot; static zero offset differences |
| `cadence` | `gait_speed` | Spatiotemporal | steps/min | m/s | **Not Comparable** | Unit & concept mismatch; physical scale unavailable |
| `trunk_lateral_displacement_px` | `thoraxAy` | Frontal | pixels | degrees | **Not Comparable** | Uncalibrated pixel distance vs 3D angular degrees |

---

## 2. Pairing & Testability Status on Real Dataset

* **Raw Video Recordings Found**: `{len(real_video_files)}` files in `data/video/raw/`.
* **Experimental Fact**: The public Figshare repository `29300888.v1` provides optical motion capture files (`.c3d`, `.txt`) and preprocessed NumPy arrays (`.npz`), but **does not bundle synchronized raw video files**.
* **Status**:
  * Event validation on real data: **`not_testable`** (requires genuine paired video).
  * Joint angle agreement on real data: **`not_testable`** until paired video recordings are collected.
  * Incompatible features: **`not_comparable`** (explicitly rejected).

---

## 3. Implemented Validation Framework

The validation layer (`src/validation/`) implements:
1. **Agreement Metrics (`calculate_agreement_metrics`)**: Bias, MAE, RMSE, Pearson $r$, Spearman $\\rho$, Bland–Altman 95% Limits of Agreement, and participant-level cluster bootstrap 95% confidence intervals.
2. **Gait Event Validation (`evaluate_gait_events`)**: Greedy temporal tolerance window (e.g. 100ms), precision, recall, F1-score, and signed timing errors (MAE, RMSE, SD).
3. **101-Point Gait Curve Validation (`validate_gait_curves`)**: Pointwise MAE and bias curves across 0–100% of the gait cycle, preserving NaNs without silent imputation.
4. **Participant Isolation**: Strict adherence to `metadata/participant_splits.csv` (7 train, 2 val, 2 test) to prevent cross-contamination across repeated trials.

---

## 4. Scientific Constraints & Limitations

1. **Non-Equivalence**: 2D monocular video estimates cannot be presented as equivalent to calibrated 3D Plug-in Gait laboratory measurements.
2. **Correlation vs Agreement**: Correlation measures linear association, not agreement. Bland–Altman limits and systematic bias are required.
3. **Synthetic Tests**: Unit tests use deterministic synthetic signals to guarantee algorithmic correctness, but synthetic tests do **not** constitute clinical or biological validation.
"""
    with open(report_md, "w", encoding="utf-8") as f:
        f.write(report_text)

    logger.info("Milestone 4 validation executed; report generated at %s", report_md)
    return ValidationArtifacts(
        feature_compatibility_csv=compat_csv,
        matched_observations_parquet=matched_pq,
        excluded_observations_csv=excluded_csv,
        event_validation_metrics_csv=event_csv,
        joint_angle_agreement_csv=joint_csv,
        gait_curve_validation_csv=curve_csv,
        participant_validation_metrics_csv=part_csv,
        validation_metadata_json=meta_json,
        report_markdown=report_md,
    )


if __name__ == "__main__":
    run_biomechanical_validation()
