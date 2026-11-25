"""Pointwise and peak comparison between 101-point video and reference gait-cycle curves."""

from typing import List, Optional
import numpy as np

from src.validation.validation_schema import CurveValidationSummary


def validate_gait_curves(
    video_curves: List[np.ndarray],
    ref_curves: List[np.ndarray],
    feature_name: str,
    reference_var: str,
    condition: str = "level_up",
    camera_view: str = "side",
) -> CurveValidationSummary:
    """
    Compare paired 101-point curves point-by-point (0% to 100% gait cycle).
    Preserves NaNs without silent interpolation.
    """
    n_pairs = min(len(video_curves), len(ref_curves))
    if n_pairs == 0:
        return CurveValidationSummary(
            feature_name=feature_name,
            reference_var=reference_var,
            condition=condition,
            camera_view=camera_view,
            n_paired_cycles=0,
        )

    mat_v = np.vstack([np.asarray(c, dtype=np.float64) for c in video_curves[:n_pairs]])
    mat_r = np.vstack([np.asarray(c, dtype=np.float64) for c in ref_curves[:n_pairs]])

    # Pointwise differences (video - reference)
    diffs = mat_v - mat_r  # shape: (n_pairs, 101)

    pointwise_mae = []
    pointwise_bias = []
    for i in range(101):
        d_col = diffs[:, i]
        valid_d = d_col[np.isfinite(d_col)]
        if valid_d.size > 0:
            pointwise_mae.append(float(np.mean(np.abs(valid_d))))
            pointwise_bias.append(float(np.mean(valid_d)))
        else:
            pointwise_mae.append(float("nan"))
            pointwise_bias.append(float("nan"))

    valid_all = diffs[np.isfinite(diffs)]
    mean_mae = float(np.mean(np.abs(valid_all))) if valid_all.size > 0 else None
    mean_rmse = float(np.sqrt(np.mean(valid_all ** 2))) if valid_all.size > 0 else None
    mean_bias = float(np.mean(valid_all)) if valid_all.size > 0 else None

    # Peak magnitude and peak timing differences
    peak_mag_diffs = []
    peak_time_diffs = []
    for v_c, r_c in zip(mat_v, mat_r):
        if np.isfinite(v_c).sum() > 10 and np.isfinite(r_c).sum() > 10:
            v_peak_val = float(np.nanmax(v_c))
            r_peak_val = float(np.nanmax(r_c))
            v_peak_idx = float(np.nanargmax(v_c))
            r_peak_idx = float(np.nanargmax(r_c))
            peak_mag_diffs.append(v_peak_val - r_peak_val)
            peak_time_diffs.append(v_peak_idx - r_peak_idx)

    mean_peak_mag = float(np.mean(peak_mag_diffs)) if peak_mag_diffs else None
    mean_peak_time = float(np.mean(peak_time_diffs)) if peak_time_diffs else None

    return CurveValidationSummary(
        feature_name=feature_name,
        reference_var=reference_var,
        condition=condition,
        camera_view=camera_view,
        n_paired_cycles=n_pairs,
        mean_curve_mae=round(mean_mae, 3) if mean_mae is not None else None,
        mean_curve_rmse=round(mean_rmse, 3) if mean_rmse is not None else None,
        mean_curve_bias=round(mean_bias, 3) if mean_bias is not None else None,
        peak_magnitude_diff_mean=round(mean_peak_mag, 3) if mean_peak_mag is not None else None,
        peak_timing_diff_mean_pct=round(mean_peak_time, 2) if mean_peak_time is not None else None,
        pointwise_mae_curve=[round(x, 3) if np.isfinite(x) else None for x in pointwise_mae],
        pointwise_bias_curve=[round(x, 3) if np.isfinite(x) else None for x in pointwise_bias],
    )
