"""Trial-level, gait-phase, and bilateral feature extraction for NPZ gait curves."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from src.core.config import AppConfig
from src.core.logging import get_logger

logger = get_logger(__name__)


def classify_completeness(
    valid_count: int,
    total_count: int,
    min_valid_samples: int,
) -> str:
    """Classify curve completeness into four explicit categories."""
    if valid_count == 0:
        return "unavailable"
    if valid_count == total_count:
        return "complete"
    if valid_count >= min_valid_samples:
        return "partially_missing"
    return "insufficiently_complete"


def extract_curve_features(
    curve: np.ndarray,
    variable_name: str,
    phase_points_pct: List[int],
    phase_intervals_pct: Dict[str, List[int]],
    min_valid_samples: int = 81,
    allow_interpolation: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Extract summary and gait-phase features from a 101-point gait-cycle curve.

    Returns:
        (feature_dict, quality_dict)
    """
    arr = np.asarray(curve, dtype=np.float64)
    total_samples = int(arr.size)
    finite_mask = np.isfinite(arr)
    valid_count = int(finite_mask.sum())
    missing_count = total_samples - valid_count
    completeness_pct = round(100.0 * valid_count / total_samples, 2) if total_samples > 0 else 0.0
    status = classify_completeness(valid_count, total_samples, min_valid_samples)
    is_reliable = status in {"complete", "partially_missing"}

    interpolated = False
    working_arr = arr.copy()
    if allow_interpolation and status == "partially_missing" and valid_count >= 2:
        x_all = np.arange(total_samples)
        working_arr[~finite_mask] = np.interp(x_all[~finite_mask], x_all[finite_mask], arr[finite_mask])
        interpolated = True

    quality_dict: Dict[str, Any] = {
        "variable_name": variable_name,
        "total_samples": total_samples,
        "valid_samples": valid_count,
        "missing_samples": missing_count,
        "completeness_pct": completeness_pct,
        "completeness_status": status,
        "is_reliable": is_reliable,
        "interpolated": interpolated,
    }

    feat_dict: Dict[str, Any] = {
        "variable_name": variable_name,
        "valid_samples": valid_count,
        "missing_samples": missing_count,
        "completeness_pct": completeness_pct,
        "completeness_status": status,
        "is_reliable": is_reliable,
    }

    if not is_reliable:
        for k in [
            "mean", "median", "std", "min", "max", "rom",
            "peak_abs_value", "peak_timing_pct", "min_timing_pct",
        ]:
            feat_dict[k] = None
        for p in phase_points_pct:
            feat_dict[f"phase_{p}_pct"] = None
        for interval_name in phase_intervals_pct:
            feat_dict[f"interval_{interval_name}_mean"] = None
        return feat_dict, quality_dict

    valid_vals = working_arr[np.isfinite(working_arr)]
    min_val = float(np.min(valid_vals))
    max_val = float(np.max(valid_vals))

    # Index of max/min across 0..100 maps directly to 0%..100% normalised gait cycle
    masked_for_max = np.where(np.isfinite(working_arr), working_arr, -np.inf)
    masked_for_min = np.where(np.isfinite(working_arr), working_arr, np.inf)
    peak_idx = int(np.argmax(masked_for_max))
    min_idx = int(np.argmin(masked_for_min))

    peak_abs = max_val if abs(max_val) >= abs(min_val) else min_val

    feat_dict.update(
        {
            "mean": float(np.mean(valid_vals)),
            "median": float(np.median(valid_vals)),
            "std": float(np.std(valid_vals, ddof=1)) if valid_vals.size > 1 else 0.0,
            "min": min_val,
            "max": max_val,
            "rom": float(max_val - min_val),
            "peak_abs_value": float(peak_abs),
            "peak_timing_pct": float(peak_idx),
            "min_timing_pct": float(min_idx),
        }
    )

    for p in phase_points_pct:
        if 0 <= p < total_samples and np.isfinite(working_arr[p]):
            feat_dict[f"phase_{p}_pct"] = float(working_arr[p])
        else:
            feat_dict[f"phase_{p}_pct"] = None

    for interval_name, bounds in phase_intervals_pct.items():
        start_idx, end_idx = int(bounds[0]), int(bounds[1])
        seg = working_arr[start_idx : end_idx + 1]
        seg_valid = seg[np.isfinite(seg)]
        feat_dict[f"interval_{interval_name}_mean"] = float(np.mean(seg_valid)) if seg_valid.size > 0 else None

    return feat_dict, quality_dict


def compute_symmetry_index(
    primary_val: Optional[float],
    contra_val: Optional[float],
    near_zero_threshold: float = 1e-3,
) -> Tuple[Optional[float], str]:
    """
    Compute percentage asymmetry using the standard Symmetry Index:
        SI (%) = 100 * (primary - contra) / (0.5 * (|primary| + |contra|))
    Returns (value_or_none, status).
    """
    if primary_val is None or contra_val is None:
        return None, "unavailable_input"
    denom = 0.5 * (abs(primary_val) + abs(contra_val))
    if denom < near_zero_threshold:
        return None, "near_zero_denominator"
    return float(100.0 * (primary_val - contra_val) / denom), "computed"


def extract_bilateral_pair(
    primary_feat: Dict[str, Any],
    contra_feat: Dict[str, Any],
    pair_cfg: Dict[str, str],
    phase_points_pct: List[int],
    near_zero_threshold: float = 1e-3,
) -> Dict[str, Any]:
    """Compute bilateral differences and asymmetry metrics for a primary/contra pair."""
    primary_var = pair_cfg["primary"]
    contra_var = pair_cfg["contralateral"]
    both_reliable = bool(primary_feat.get("is_reliable")) and bool(contra_feat.get("is_reliable"))

    row: Dict[str, Any] = {
        "joint": pair_cfg["joint"],
        "axis": pair_cfg["axis"],
        "primary_var": primary_var,
        "contra_var": contra_var,
        "mapping_note": "primary=ipsilateral/force-plate-referenced; contra=contralateral",
        "is_reliable": both_reliable,
    }

    if not both_reliable:
        row.update(
            {
                "mean_diff": None,
                "abs_mean_diff": None,
                "peak_diff": None,
                "rom_diff": None,
                "peak_timing_diff_pct": None,
                "mean_asymmetry_pct": None,
                "mean_asymmetry_status": "unreliable_input",
                "rom_asymmetry_pct": None,
                "rom_asymmetry_status": "unreliable_input",
            }
        )
        for p in phase_points_pct:
            row[f"phase_{p}_diff"] = None
        return row

    mean_diff = primary_feat["mean"] - contra_feat["mean"]
    peak_diff = primary_feat["max"] - contra_feat["max"]
    rom_diff = primary_feat["rom"] - contra_feat["rom"]
    timing_diff = primary_feat["peak_timing_pct"] - contra_feat["peak_timing_pct"]

    mean_asym, mean_asym_status = compute_symmetry_index(
        primary_feat["mean"], contra_feat["mean"], near_zero_threshold
    )
    rom_asym, rom_asym_status = compute_symmetry_index(
        primary_feat["rom"], contra_feat["rom"], near_zero_threshold
    )

    row.update(
        {
            "mean_diff": float(mean_diff),
            "abs_mean_diff": float(abs(mean_diff)),
            "peak_diff": float(peak_diff),
            "rom_diff": float(rom_diff),
            "peak_timing_diff_pct": float(timing_diff),
            "mean_asymmetry_pct": mean_asym,
            "mean_asymmetry_status": mean_asym_status,
            "rom_asymmetry_pct": rom_asym,
            "rom_asymmetry_status": rom_asym_status,
        }
    )

    for p in phase_points_pct:
        pv = primary_feat.get(f"phase_{p}_pct")
        cv = contra_feat.get(f"phase_{p}_pct")
        row[f"phase_{p}_diff"] = float(pv - cv) if (pv is not None and cv is not None) else None

    return row


def _curve_group_for_var(var_name: str) -> Optional[str]:
    if var_name.startswith("kneeA"):
        return "knee_angles"
    if var_name.startswith("hipA"):
        return "hip_angles"
    if var_name.startswith("ankleA"):
        return "ankle_angles"
    if var_name.endswith(("Mx", "My", "Mz", "Px", "Py", "Pz")):
        return "joint_moments_powers"
    return None


def run_feature_extraction(cfg: Optional[AppConfig] = None) -> Dict[str, Path]:
    """Run trial-level, bilateral, and curve-preservation extraction across all usable trials."""
    cfg = cfg or AppConfig()
    trial_index_path = cfg.metadata_dir / "trial_index.csv"
    if not trial_index_path.exists():
        raise FileNotFoundError(f"Missing Milestone 1 trial index: {trial_index_path}")

    trial_index = pd.read_csv(trial_index_path)
    usable_trials = trial_index[trial_index["validation_status"] != "invalid"].copy()
    excluded_count = len(trial_index) - len(usable_trials)
    if excluded_count > 0:
        logger.warning("Excluded %d invalid trials from feature extraction.", excluded_count)

    feat_cfg = cfg.feature_cfg.get("features", {})
    target_vars: List[str] = (
        feat_cfg.get("angles", []) + feat_cfg.get("moments", []) + feat_cfg.get("powers", [])
    )
    phase_points = feat_cfg.get("gait_phases", {}).get("points_pct", [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
    phase_intervals = feat_cfg.get("gait_phases", {}).get("intervals_pct", {})
    missing_cfg = feat_cfg.get("missing_data", {})
    min_valid_samples = int(missing_cfg.get("min_valid_samples", 81))
    allow_interp = bool(missing_cfg.get("allow_interpolation", False))
    bilateral_pairs = feat_cfg.get("bilateral_pairs", [])
    near_zero_thresh = float(feat_cfg.get("asymmetry", {}).get("near_zero_threshold", 1e-3))

    summary_rows: List[Dict[str, Any]] = []
    quality_rows: List[Dict[str, Any]] = []
    bilateral_rows: List[Dict[str, Any]] = []

    curve_buffers: Dict[str, List[Dict[str, Any]]] = {
        "knee_angles": [],
        "hip_angles": [],
        "ankle_angles": [],
        "joint_moments_powers": [],
    }
    pct_cols = [f"pct_{i}" for i in range(cfg.gait_cycle_points)]

    for _, trow in usable_trials.iterrows():
        npz_path = cfg.project_root / str(trow["file_path"])
        trial_id = str(trow["trial_id"])
        participant_id = str(trow["participant_id"])
        condition = str(trow["condition"])
        gait_speed = trow["gait_speed"]

        trial_feats_by_var: Dict[str, Dict[str, Any]] = {}
        with np.load(npz_path, allow_pickle=True) as data:
            for var in target_vars:
                if var not in data:
                    continue
                curve = data[var]
                f_dict, q_dict = extract_curve_features(
                    curve=curve,
                    variable_name=var,
                    phase_points_pct=phase_points,
                    phase_intervals_pct=phase_intervals,
                    min_valid_samples=min_valid_samples,
                    allow_interpolation=allow_interp,
                )
                base_meta = {
                    "trial_id": trial_id,
                    "participant_id": participant_id,
                    "condition": condition,
                    "gait_speed": gait_speed,
                }
                summary_rows.append({**base_meta, **f_dict})
                quality_rows.append({**base_meta, **q_dict})
                trial_feats_by_var[var] = f_dict

                grp = _curve_group_for_var(var)
                if grp is not None:
                    c_row = {**base_meta, "variable_name": var}
                    for idx, col in enumerate(pct_cols):
                        val = float(curve[idx])
                        c_row[col] = val if np.isfinite(val) else np.nan
                    curve_buffers[grp].append(c_row)

        # Bilateral extraction
        for pair in bilateral_pairs:
            p_var = pair["primary"]
            c_var = pair["contralateral"]
            if p_var in trial_feats_by_var and c_var in trial_feats_by_var:
                b_row = extract_bilateral_pair(
                    trial_feats_by_var[p_var],
                    trial_feats_by_var[c_var],
                    pair,
                    phase_points,
                    near_zero_threshold=near_zero_thresh,
                )
                bilateral_rows.append(
                    {
                        "trial_id": trial_id,
                        "participant_id": participant_id,
                        "condition": condition,
                        "gait_speed": gait_speed,
                        **b_row,
                    }
                )

    # Save trial_features outputs
    cfg.trial_features_dir.mkdir(parents=True, exist_ok=True)
    summary_df = pd.DataFrame(summary_rows)
    quality_df = pd.DataFrame(quality_rows)
    bilateral_df = pd.DataFrame(bilateral_rows)

    summary_csv = cfg.trial_features_dir / "trial_feature_summary.csv"
    summary_pq = cfg.trial_features_dir / "trial_features.parquet"
    quality_csv = cfg.trial_features_dir / "trial_feature_quality.csv"
    bilateral_csv = cfg.trial_features_dir / "bilateral_features.csv"
    bilateral_pq = cfg.trial_features_dir / "bilateral_features.parquet"

    summary_df.to_csv(summary_csv, index=False)
    summary_df.to_parquet(summary_pq, index=False)
    quality_df.to_csv(quality_csv, index=False)
    bilateral_df.to_csv(bilateral_csv, index=False)
    bilateral_df.to_parquet(bilateral_pq, index=False)

    # Save preserved 101-point curves per joint group
    for grp, rows in curve_buffers.items():
        grp_dir = cfg.gait_curves_dir / grp
        grp_dir.mkdir(parents=True, exist_ok=True)
        grp_df = pd.DataFrame(rows)
        grp_df.to_parquet(grp_dir / f"{grp}_curves.parquet", index=False)

    logger.info(
        "Extracted %d trial-variable feature rows and %d bilateral rows across %d trials.",
        len(summary_df),
        len(bilateral_df),
        len(usable_trials),
    )

    return {
        "trial_feature_summary_csv": summary_csv,
        "trial_features_parquet": summary_pq,
        "trial_feature_quality_csv": quality_csv,
        "bilateral_features_csv": bilateral_csv,
        "bilateral_features_parquet": bilateral_pq,
    }


if __name__ == "__main__":
    run_feature_extraction()
