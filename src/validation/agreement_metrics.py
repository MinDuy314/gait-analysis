"""Statistical agreement, Bland-Altman, correlation, and bootstrap confidence intervals."""

from typing import List, Optional, Tuple
import numpy as np
from scipy import stats

from src.validation.validation_schema import AgreementMetrics


def calculate_agreement_metrics(
    video_vals: np.ndarray,
    ref_vals: np.ndarray,
    feature_name: str,
    camera_view: str = "side",
    condition: str = "all",
    units: str = "degrees",
    participant_ids: Optional[List[str]] = None,
    n_bootstrap: int = 1000,
    random_seed: int = 42,
) -> AgreementMetrics:
    """
    Calculate comprehensive agreement metrics:
    Bias, MAE, RMSE, Pearson r, Spearman rho, Bland-Altman LoA, and bootstrap MAE CI.
    """
    v_arr = np.asarray(video_vals, dtype=np.float64)
    r_arr = np.asarray(ref_vals, dtype=np.float64)

    valid_mask = np.isfinite(v_arr) & np.isfinite(r_arr)
    v_clean = v_arr[valid_mask]
    r_clean = r_arr[valid_mask]
    n_obs = int(v_clean.size)

    if participant_ids is not None:
        p_clean = [p for p, m in zip(participant_ids, valid_mask) if m]
        n_part = len(set(p_clean))
    else:
        n_part = 1 if n_obs > 0 else 0

    if n_obs < 3:
        return AgreementMetrics(
            feature_name=feature_name,
            camera_view=camera_view,
            condition=condition,
            units=units,
            n_observations=n_obs,
            n_participants=n_part,
            interpretation_note="Insufficient observations (< 3) to compute statistical agreement metrics.",
        )

    diffs = v_clean - r_clean
    mean_bias = float(np.mean(diffs))
    mae = float(np.mean(np.abs(diffs)))
    rmse = float(np.sqrt(np.mean(diffs ** 2)))
    sd_diff = float(np.std(diffs, ddof=1)) if n_obs > 1 else 0.0

    lower_loa = mean_bias - 1.96 * sd_diff
    upper_loa = mean_bias + 1.96 * sd_diff

    # Correlations
    if np.all(v_clean == v_clean[0]) or np.all(r_clean == r_clean[0]):
        pearson_r, p_val = None, None
        spearman_rho, sp_val = None, None
    else:
        r_res = stats.pearsonr(v_clean, r_clean)
        pearson_r, p_val = float(r_res.statistic), float(r_res.pvalue)
        s_res = stats.spearmanr(v_clean, r_clean)
        spearman_rho, sp_val = float(s_res.statistic), float(s_res.pvalue)

    # Participant-level or observation-level bootstrap for MAE 95% CI
    rng = np.random.default_rng(random_seed)
    boot_maes = []
    if participant_ids is not None and n_part >= 3:
        # Cluster bootstrap by participant to avoid treating repeated measures as independent
        unique_parts = list(set(p_clean))
        p_arr = np.array(p_clean)
        for _ in range(n_bootstrap):
            sampled_parts = rng.choice(unique_parts, size=len(unique_parts), replace=True)
            boot_diffs = []
            for sp in sampled_parts:
                boot_diffs.extend(diffs[p_arr == sp])
            if boot_diffs:
                boot_maes.append(np.mean(np.abs(boot_diffs)))
    else:
        for _ in range(n_bootstrap):
            idx = rng.choice(n_obs, size=n_obs, replace=True)
            boot_maes.append(np.mean(np.abs(diffs[idx])))

    if boot_maes:
        ci_low, ci_high = np.percentile(boot_maes, [2.5, 97.5])
        ci_lower = float(ci_low)
        ci_upper = float(ci_high)
    else:
        ci_lower, ci_upper = None, None

    return AgreementMetrics(
        feature_name=feature_name,
        camera_view=camera_view,
        condition=condition,
        units=units,
        n_observations=n_obs,
        n_participants=n_part,
        mean_bias=round(mean_bias, 3),
        mae=round(mae, 3),
        rmse=round(rmse, 3),
        pearson_r=round(pearson_r, 3) if pearson_r is not None else None,
        pearson_p_value=round(p_val, 4) if p_val is not None else None,
        spearman_rho=round(spearman_rho, 3) if spearman_rho is not None else None,
        spearman_p_value=round(sp_val, 4) if sp_val is not None else None,
        bland_altman_lower_loa=round(lower_loa, 3),
        bland_altman_upper_loa=round(upper_loa, 3),
        bland_altman_sd=round(sd_diff, 3),
        bootstrap_mae_ci_lower=round(ci_lower, 3) if ci_lower is not None else None,
        bootstrap_mae_ci_upper=round(ci_upper, 3) if ci_upper is not None else None,
        interpretation_note="Agreement evaluated using paired differences (video - reference).",
    )
