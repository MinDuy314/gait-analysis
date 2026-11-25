"""Reference distribution and 101-point gait-cycle reference curve builder."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.core.config import AppConfig
from src.core.logging import get_logger

logger = get_logger(__name__)

SUMMARY_METRICS = [
    "mean",
    "median",
    "std",
    "min",
    "max",
    "rom",
    "peak_abs_value",
    "peak_timing_pct",
    "min_timing_pct",
]


def _parse_var_meta(var_name: str) -> Tuple[str, str, str]:
    is_contra = var_name.endswith("_contra")
    side_role = "contralateral" if is_contra else "primary"
    base = var_name.replace("_contra", "")
    axis = base[-1].upper() if base[-1] in {"x", "y", "z"} else "N/A"
    joint = base[:-2] if len(base) > 2 else base
    return joint, side_role, axis


def _compute_stats_row(
    values: np.ndarray,
    percentiles: List[int],
    min_samples: int,
    min_for_percentiles: int,
) -> Dict[str, Any]:
    valid = values[np.isfinite(values)]
    n = int(valid.size)
    if n < min_samples or n == 0:
        row: Dict[str, Any] = {
            "availability_status": "insufficient_samples",
            "mean": None,
            "std": None,
            "median": None,
            "iqr": None,
            "min": None,
            "max": None,
        }
        for p in percentiles:
            row[f"p{p}"] = None
        return row

    q25, q75 = np.percentile(valid, [25, 75])
    row = {
        "availability_status": "available",
        "mean": float(np.mean(valid)),
        "std": float(np.std(valid, ddof=1)) if n > 1 else 0.0,
        "median": float(np.median(valid)),
        "iqr": float(q75 - q25),
        "min": float(np.min(valid)),
        "max": float(np.max(valid)),
    }
    if n >= min_for_percentiles:
        pct_vals = np.percentile(valid, percentiles)
        for p, pv in zip(percentiles, pct_vals):
            row[f"p{p}"] = float(pv)
    else:
        for p in percentiles:
            row[f"p{p}"] = None
    return row


def build_reference_distributions(cfg: Optional[AppConfig] = None) -> Dict[str, Path]:
    """Build trial-level, participant-level, and 101-point gait-cycle reference distributions."""
    cfg = cfg or AppConfig()
    summary_path = cfg.trial_features_dir / "trial_feature_summary.csv"
    if not summary_path.exists():
        raise FileNotFoundError(f"Missing trial_feature_summary.csv at {summary_path}")

    df = pd.read_csv(summary_path)
    reliable_df = df[df["is_reliable"] == True].copy()  # noqa: E712

    ref_cfg = cfg.feature_cfg.get("reference", {})
    percentiles = [int(p) for p in ref_cfg.get("percentiles", [5, 25, 50, 75, 95])]
    min_trials = int(ref_cfg.get("min_trials_for_stats", 5))
    min_participants = int(ref_cfg.get("min_participants_for_stats", 3))
    min_part_pct = int(ref_cfg.get("min_participants_for_percentiles", 5))

    phase_cols = [c for c in df.columns if c.startswith("phase_") and c.endswith("_pct")]
    metric_cols = SUMMARY_METRICS + phase_cols

    trial_dist_rows: List[Dict[str, Any]] = []
    part_dist_rows: List[Dict[str, Any]] = []

    for (condition, var_name), grp in reliable_df.groupby(["condition", "variable_name"]):
        joint, side_role, axis = _parse_var_meta(str(var_name))
        n_trials_grp = int(len(grp))
        n_part_grp = int(grp["participant_id"].nunique())

        # Participant-aggregated table for this (condition, variable_name)
        part_means = grp.groupby("participant_id")[metric_cols].mean(numeric_only=True)

        for m in metric_cols:
            # 1. Trial-level distribution
            vals_t = grp[m].dropna().to_numpy(dtype=np.float64)
            stats_t = _compute_stats_row(vals_t, percentiles, min_trials, min_trials)
            trial_dist_rows.append(
                {
                    "condition": condition,
                    "variable_name": var_name,
                    "joint": joint,
                    "side_role": side_role,
                    "axis": axis,
                    "metric": m,
                    "n_trials": int(vals_t.size),
                    "n_participants": int(grp.loc[grp[m].notna(), "participant_id"].nunique()),
                    **stats_t,
                }
            )

            # 2. Participant-level distribution (equal weight per participant)
            vals_p = part_means[m].dropna().to_numpy(dtype=np.float64)
            stats_p = _compute_stats_row(vals_p, percentiles, min_participants, min_part_pct)
            part_dist_rows.append(
                {
                    "condition": condition,
                    "variable_name": var_name,
                    "joint": joint,
                    "side_role": side_role,
                    "axis": axis,
                    "metric": m,
                    "n_participants": int(vals_p.size),
                    "total_contributing_trials": int(grp[m].notna().sum()),
                    "total_condition_trials": n_trials_grp,
                    "total_condition_participants": n_part_grp,
                    **stats_p,
                }
            )

    cfg.reference_dir.mkdir(parents=True, exist_ok=True)
    trial_ref_path = cfg.reference_dir / "trial_reference_distributions.csv"
    part_ref_path = cfg.reference_dir / "participant_reference_distributions.csv"

    pd.DataFrame(trial_dist_rows).to_csv(trial_ref_path, index=False)
    pd.DataFrame(part_dist_rows).to_csv(part_ref_path, index=False)

    # 3. 101-point Gait-cycle reference curves
    pct_cols = [f"pct_{i}" for i in range(cfg.gait_cycle_points)]
    curve_summary_rows: List[Dict[str, Any]] = []

    for curve_file in sorted(cfg.gait_curves_dir.glob("*/*_curves.parquet")):
        if curve_file.name.endswith("_reference_curves.parquet"):
            continue
        grp_name = curve_file.parent.name
        cdf = pd.read_parquet(curve_file)
        ref_curve_rows: List[Dict[str, Any]] = []

        for (condition, var_name), sub in cdf.groupby(["condition", "variable_name"]):
            joint, side_role, axis = _parse_var_meta(str(var_name))
            # Aggregate per participant first at each point
            part_curves = sub.groupby("participant_id")[pct_cols].mean(numeric_only=True)
            mat_trials = sub[pct_cols].to_numpy(dtype=np.float64)
            mat_parts = part_curves[pct_cols].to_numpy(dtype=np.float64)

            n_trials_pt = np.sum(np.isfinite(mat_trials), axis=0)
            n_parts_pt = np.sum(np.isfinite(mat_parts), axis=0)

            mean_curve = np.full(cfg.gait_cycle_points, np.nan)
            std_curve = np.full(cfg.gait_cycle_points, np.nan)
            median_curve = np.full(cfg.gait_cycle_points, np.nan)
            iqr_curve = np.full(cfg.gait_cycle_points, np.nan)
            p5_curve = np.full(cfg.gait_cycle_points, np.nan)
            p95_curve = np.full(cfg.gait_cycle_points, np.nan)

            for i in range(cfg.gait_cycle_points):
                col_p = mat_parts[:, i]
                valid_p = col_p[np.isfinite(col_p)]
                if valid_p.size >= min_participants:
                    mean_curve[i] = float(np.mean(valid_p))
                    std_curve[i] = float(np.std(valid_p, ddof=1)) if valid_p.size > 1 else 0.0
                    median_curve[i] = float(np.median(valid_p))
                    q25, q75 = np.percentile(valid_p, [25, 75])
                    iqr_curve[i] = float(q75 - q25)
                if valid_p.size >= min_part_pct:
                    p5_curve[i] = float(np.percentile(valid_p, 5))
                    p95_curve[i] = float(np.percentile(valid_p, 95))

            for stat_name, arr in [
                ("participant_mean", mean_curve),
                ("participant_std", std_curve),
                ("participant_median", median_curve),
                ("participant_iqr", iqr_curve),
                ("participant_p5", p5_curve),
                ("participant_p95", p95_curve),
                ("n_trials", n_trials_pt.astype(float)),
                ("n_participants", n_parts_pt.astype(float)),
            ]:
                row = {
                    "condition": condition,
                    "variable_name": var_name,
                    "joint": joint,
                    "side_role": side_role,
                    "axis": axis,
                    "stat_type": stat_name,
                }
                for i, col in enumerate(pct_cols):
                    row[col] = arr[i]
                ref_curve_rows.append(row)

            curve_summary_rows.append(
                {
                    "curve_group": grp_name,
                    "condition": condition,
                    "variable_name": var_name,
                    "min_n_trials_across_cycle": int(n_trials_pt.min()),
                    "max_n_trials_across_cycle": int(n_trials_pt.max()),
                    "min_n_participants_across_cycle": int(n_parts_pt.min()),
                    "max_n_participants_across_cycle": int(n_parts_pt.max()),
                    "points_meeting_min_participants": int(np.sum(n_parts_pt >= min_participants)),
                }
            )

        out_curve_pq = curve_file.parent / f"{grp_name}_reference_curves.parquet"
        pd.DataFrame(ref_curve_rows).to_parquet(out_curve_pq, index=False)

    curve_summary_path = cfg.reference_dir / "reference_curve_summary.csv"
    pd.DataFrame(curve_summary_rows).to_csv(curve_summary_path, index=False)

    # 4. Reference metadata JSON
    meta_path = cfg.reference_dir / "reference_metadata.json"
    meta_payload = {
        "dataset_name": cfg.dataset_cfg.get("dataset", {}).get("name"),
        "dataset_version": cfg.dataset_cfg.get("dataset", {}).get("version"),
        "participants_included": sorted(reliable_df["participant_id"].unique().tolist()),
        "n_participants": int(reliable_df["participant_id"].nunique()),
        "n_trials_processed": int(reliable_df["trial_id"].nunique()),
        "conditions": sorted(reliable_df["condition"].unique().tolist()),
        "thresholds": {
            "min_trials_for_stats": min_trials,
            "min_participants_for_stats": min_participants,
            "min_participants_for_percentiles": min_part_pct,
            "percentiles": percentiles,
        },
        "limitations": [
            "Dataset contains 11 participants with NPZ data (Ref03 and Ref04 unavailable in NPZ).",
            "Distributions reflect this specific research cohort and must NOT be presented as universal clinical norms.",
            "Conditions are kept strictly separate and must not be pooled.",
        ],
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_payload, f, indent=2)

    logger.info("Generated reference distributions and 101-point reference curves in %s", cfg.reference_dir)
    return {
        "trial_reference_distributions_csv": trial_ref_path,
        "participant_reference_distributions_csv": part_ref_path,
        "reference_curve_summary_csv": curve_summary_path,
        "reference_metadata_json": meta_path,
    }


if __name__ == "__main__":
    build_reference_distributions()
