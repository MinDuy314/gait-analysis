"""Gait cycle segmentation and 101-point temporal normalization."""

from typing import List, Optional
import numpy as np
from pydantic import BaseModel, Field

from src.gait_events.gait_event_detector import GaitEvent


class GaitCycle(BaseModel):
    """Segmented complete or incomplete gait cycle."""

    cycle_id: str
    side: str
    is_complete: bool
    start_frame: int
    end_frame: int
    start_timestamp_s: float
    end_timestamp_s: float
    duration_s: float
    event_confidence: float
    quality_status: str = "acceptable"
    reason_if_incomplete: Optional[str] = None


def segment_gait_cycles(events: List[GaitEvent]) -> List[GaitCycle]:
    """Segment gait cycles between consecutive same-side foot strikes."""
    cycles: List[GaitCycle] = []

    for side in ["left", "right"]:
        strikes = [e for e in events if e.side == side and e.event_type == "foot_strike"]
        if len(strikes) < 2:
            continue

        for i in range(len(strikes) - 1):
            e_start = strikes[i]
            e_end = strikes[i + 1]
            duration = e_end.timestamp_s - e_start.timestamp_s
            avg_conf = (e_start.confidence + e_end.confidence) / 2.0

            # Anatomical physiological check: adult gait cycle between 0.5s and 2.5s
            is_plausible = (0.45 <= duration <= 2.5)
            cycles.append(
                GaitCycle(
                    cycle_id=f"{side}_cycle_{i+1}_{e_start.frame_index}_{e_end.frame_index}",
                    side=side,
                    is_complete=is_plausible,
                    start_frame=e_start.frame_index,
                    end_frame=e_end.frame_index,
                    start_timestamp_s=e_start.timestamp_s,
                    end_timestamp_s=e_end.timestamp_s,
                    duration_s=round(duration, 3),
                    event_confidence=round(avg_conf, 2),
                    quality_status="acceptable" if is_plausible else "implausible_duration",
                    reason_if_incomplete=None if is_plausible else f"Cycle duration {duration:.2f}s outside physiological range",
                )
            )

    cycles.sort(key=lambda c: c.start_timestamp_s)
    return cycles


def normalize_cycle_trajectory(
    raw_trajectory: np.ndarray,
    n_points: int = 101,
) -> np.ndarray:
    """
    Temporally resample a cycle trajectory to 101 samples (0% to 100% gait cycle).
    Uses linear interpolation across normalized time percentage.
    """
    arr = np.asarray(raw_trajectory, dtype=np.float64)
    if arr.size < 2:
        return np.full(n_points, np.nan)

    x_orig = np.linspace(0.0, 100.0, num=arr.size)
    x_target = np.linspace(0.0, 100.0, num=n_points)
    return np.interp(x_target, x_orig, arr)
