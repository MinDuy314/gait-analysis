"""Research-oriented Matplotlib visualizations for Milestone 2 NPZ reference data."""

from pathlib import Path
from typing import List, Optional
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.core.config import AppConfig
from src.core.logging import get_logger

logger = get_logger(__name__)


def generate_milestone2_figures(cfg: Optional[AppConfig] = None) -> List[Path]:
    """Generate all 7 required research visualizations under outputs/figures/."""
    cfg = cfg or AppConfig()
    fig_dir = cfg.figures_dir
    fig_dir.mkdir(parents=True, exist_ok=True)
    generated: List[Path] = []

    pct_x = np.arange(cfg.gait_cycle_points)
    pct_cols = [f"pct_{i}" for i in range(cfg.gait_cycle_points)]

    knee_ref = pd.read_parquet(cfg.gait_curves_dir / "knee_angles" / "knee_angles_reference_curves.parquet")
    hip_ref = pd.read_parquet(cfg.gait_curves_dir / "hip_angles" / "hip_angles_reference_curves.parquet")
    ankle_ref = pd.read_parquet(cfg.gait_curves_dir / "ankle_angles" / "ankle_angles_reference_curves.parquet")
    summary_df = pd.read_csv(cfg.trial_features_dir / "trial_feature_summary.csv")
    missing_df = pd.read_csv(cfg.qc_dir / "missing_data.csv")
    trial_df = pd.read_csv(cfg.metadata_dir / "trial_index.csv")

    # 1. Mean gait-cycle curves with variability bands (level_up)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharex=True)
    for ax, (ref_df, var, title) in zip(
        axes,
        [
            (hip_ref, "hipAx", "Hip Sagittal (hipAx)"),
            (knee_ref, "kneeAx", "Knee Flexion/Extension (kneeAx)"),
            (ankle_ref, "ankleAx", "Ankle Sagittal (ankleAx)"),
        ],
    ):
        sub = ref_df[(ref_df["condition"] == "level_up") & (ref_df["variable_name"] == var)]
        mean_y = sub[sub["stat_type"] == "participant_mean"][pct_cols].to_numpy().ravel()
        std_y = sub[sub["stat_type"] == "participant_std"][pct_cols].to_numpy().ravel()
        n_p = int(sub[sub["stat_type"] == "n_participants"][pct_cols].to_numpy().ravel().min())
        n_t = int(sub[sub["stat_type"] == "n_trials"][pct_cols].to_numpy().ravel().min())
        ax.plot(pct_x, mean_y, color="tab:blue", linewidth=2, label="Participant Mean")
        ax.fill_between(pct_x, mean_y - std_y, mean_y + std_y, color="tab:blue", alpha=0.25, label="±1 SD")
        ax.set_title(f"{title}\nlevel_up (n_part={n_p}, n_trials={n_t})")
        ax.set_xlabel("Gait Cycle (%)")
        ax.set_ylabel("Angle (deg)")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("1. Mean Gait-Cycle Curves with Between-Participant Variability (±1 SD)", y=1.02)
    fig.tight_layout()
    p1 = fig_dir / "01_mean_gait_cycle_variability.png"
    fig.savefig(p1, dpi=150, bbox_inches="tight")
    plt.close(fig)
    generated.append(p1)

    # 2. Joint-angle curves across walking conditions (kneeAx)
    fig, ax = plt.subplots(figsize=(9, 5))
    for cond, grp in knee_ref[knee_ref["variable_name"] == "kneeAx"].groupby("condition"):
        mean_y = grp[grp["stat_type"] == "participant_mean"][pct_cols].to_numpy().ravel()
        n_p = int(grp[grp["stat_type"] == "n_participants"][pct_cols].to_numpy().ravel().min())
        ax.plot(pct_x, mean_y, linewidth=2, label=f"{cond} (n_part={n_p})")
    ax.set_title("2. Knee Flexion/Extension (kneeAx) Across Walking Conditions")
    ax.set_xlabel("Gait Cycle (%)")
    ax.set_ylabel("Angle (deg, + = flexion)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    p2 = fig_dir / "02_knee_flexion_across_conditions.png"
    fig.savefig(p2, dpi=150)
    plt.close(fig)
    generated.append(p2)

    # 3. Left-right / Primary-Contralateral comparison curves (level_up)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharex=True)
    for ax, (ref_df, v_prim, v_cont, title) in zip(
        axes,
        [
            (knee_ref, "kneeAx", "kneeAx_contra", "Knee Sagittal (kneeAx vs contra)"),
            (hip_ref, "hipAx", "hipAx_contra", "Hip Sagittal (hipAx vs contra)"),
        ],
    ):
        for v, lbl, col in [(v_prim, "Primary", "tab:blue"), (v_cont, "Contralateral", "tab:orange")]:
            sub = ref_df[(ref_df["condition"] == "level_up") & (ref_df["variable_name"] == v)]
            m = sub[sub["stat_type"] == "participant_mean"][pct_cols].to_numpy().ravel()
            s = sub[sub["stat_type"] == "participant_std"][pct_cols].to_numpy().ravel()
            ax.plot(pct_x, m, color=col, linewidth=2, label=f"{lbl} ({v})")
            ax.fill_between(pct_x, m - s, m + s, color=col, alpha=0.18)
        ax.set_title(f"{title} — level_up")
        ax.set_xlabel("Gait Cycle (%)")
        ax.set_ylabel("Angle (deg)")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
    fig.suptitle("3. Primary vs Contralateral Mean Curves (level_up)", y=1.02)
    fig.tight_layout()
    p3 = fig_dir / "03_bilateral_comparison_curves.png"
    fig.savefig(p3, dpi=150, bbox_inches="tight")
    plt.close(fig)
    generated.append(p3)

    # 4. Participant-level distributions (kneeAx ROM across conditions)
    knee_rom = summary_df[(summary_df["variable_name"] == "kneeAx") & (summary_df["is_reliable"] == True)]  # noqa: E712
    part_rom = knee_rom.groupby(["condition", "participant_id"])["rom"].mean().reset_index()
    conditions_sorted = sorted(part_rom["condition"].unique())
    data_by_cond = [part_rom[part_rom["condition"] == c]["rom"].to_numpy() for c in conditions_sorted]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.boxplot(data_by_cond, tick_labels=conditions_sorted)
    ax.set_title("4. Participant-Level Knee Flexion/Extension ROM Distribution by Condition (n=11 participants)")
    ax.set_xlabel("Walking Condition")
    ax.set_ylabel("Range of Motion (deg)")
    ax.grid(True, axis="y", alpha=0.3)
    plt.xticks(rotation=20)
    fig.tight_layout()
    p4 = fig_dir / "04_participant_level_distributions.png"
    fig.savefig(p4, dpi=150)
    plt.close(fig)
    generated.append(p4)

    # 5. Missing-data summaries
    fig, ax = plt.subplots(figsize=(9, 4.5))
    if not missing_df.empty:
        cat_counts = missing_df["category"].value_counts()
        cat_counts.plot(kind="bar", ax=ax, color="tab:red", alpha=0.8)
    ax.set_title("5. Missing Data / NaN Occurrences by Variable Category (Across 658 Trials)")
    ax.set_xlabel("Variable Category")
    ax.set_ylabel("Affected Trial-Variable Records")
    ax.grid(True, axis="y", alpha=0.3)
    plt.xticks(rotation=0)
    fig.tight_layout()
    p5 = fig_dir / "05_missing_data_summary.png"
    fig.savefig(p5, dpi=150)
    plt.close(fig)
    generated.append(p5)

    # 6. Trial counts by condition
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    t_counts = trial_df["condition"].value_counts().sort_index()
    t_counts.plot(kind="bar", ax=ax, color="tab:green", alpha=0.8)
    ax.set_title(f"6. Trial Counts by Walking Condition (Total={len(trial_df)} trials)")
    ax.set_xlabel("Walking Condition")
    ax.set_ylabel("Number of Trials")
    ax.grid(True, axis="y", alpha=0.3)
    plt.xticks(rotation=20)
    fig.tight_layout()
    p6 = fig_dir / "06_trial_counts_by_condition.png"
    fig.savefig(p6, dpi=150)
    plt.close(fig)
    generated.append(p6)

    # 7. Participant counts by condition
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    p_counts = trial_df.groupby("condition")["participant_id"].nunique().sort_index()
    p_counts.plot(kind="bar", ax=ax, color="tab:purple", alpha=0.8)
    ax.set_title("7. Participant Counts by Walking Condition (Max=11 NPZ Participants)")
    ax.set_xlabel("Walking Condition")
    ax.set_ylabel("Number of Unique Participants")
    ax.set_ylim(0, 13)
    ax.grid(True, axis="y", alpha=0.3)
    plt.xticks(rotation=20)
    fig.tight_layout()
    p7 = fig_dir / "07_participant_counts_by_condition.png"
    fig.savefig(p7, dpi=150)
    plt.close(fig)
    generated.append(p7)

    logger.info("Generated %d figures in %s", len(generated), fig_dir)
    return generated
