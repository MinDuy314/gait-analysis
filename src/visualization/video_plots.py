"""Diagnostic video visualizer: overlays landmark confidence, trajectories, and events."""

from pathlib import Path
from typing import List, Optional
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.core.config import AppConfig
from src.video.video_pipeline_runner import VideoAnalysisResult


def plot_video_diagnostics(
    result: VideoAnalysisResult,
    output_dir: Optional[Path] = None,
) -> List[Path]:
    """Generate diagnostic visualization plots for video pose, events, and gait cycles."""
    out_dir = output_dir or (AppConfig().figures_dir / "video_diagnostics")
    out_dir.mkdir(parents=True, exist_ok=True)
    generated: List[Path] = []

    rec_id = result.recording_id

    # 1. Gait events and cycles timeline
    fig, ax = plt.subplots(figsize=(10, 3.5))
    for ev in result.gait_events:
        col = "tab:blue" if ev.side == "left" else "tab:orange"
        marker = "^" if ev.event_type == "foot_strike" else "v"
        ax.scatter(ev.timestamp_s, 1 if ev.side == "left" else 2, color=col, marker=marker, s=80, label=f"{ev.side}_{ev.event_type}")

    for cyc in result.gait_cycles:
        y_pos = 1 if cyc.side == "left" else 2
        col = "green" if cyc.is_complete else "red"
        ax.hlines(y=y_pos + 0.15, xmin=cyc.start_timestamp_s, xmax=cyc.end_timestamp_s, color=col, linewidth=3, alpha=0.6)

    ax.set_yticks([1, 2])
    ax.set_yticklabels(["Left Side", "Right Side"])
    ax.set_xlabel("Time (seconds)")
    ax.set_title(f"Gait Events & Cycles Timeline ({rec_id} | view: {result.camera_view.predicted_view})")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    p1 = out_dir / f"{rec_id}_event_timeline.png"
    fig.savefig(p1, dpi=150)
    plt.close(fig)
    generated.append(p1)

    # 2. Normalised 101-point video kinematic curve
    curves = [m for m in result.measurements if m.normalized_101_curve is not None]
    if curves:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        pct_x = np.arange(101)
        for c in curves:
            ax.plot(pct_x, c.normalized_101_curve, linewidth=2, label=f"{c.feature_name} (ROM={c.value}°)")
        ax.set_xlabel("Gait Cycle (%)")
        ax.set_ylabel("Planar Angle (degrees)")
        ax.set_title(f"Video-Derived 101-Point Joint Kinematics ({rec_id})")
        ax.grid(True, alpha=0.3)
        ax.legend()
        fig.tight_layout()
        p2 = out_dir / f"{rec_id}_normalized_kinematics.png"
        fig.savefig(p2, dpi=150)
        plt.close(fig)
        generated.append(p2)

    return generated
