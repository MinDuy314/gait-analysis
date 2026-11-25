"""Gait event detection (Foot Strike and Foot Off) from kinematic landmark trajectories."""

from typing import Dict, List, Optional
import numpy as np
from pydantic import BaseModel, Field

from src.gait_events.signal_processing import butter_lowpass_filter, detect_extrema_events
from src.pose_estimation.landmark_schema import FramePose


class GaitEvent(BaseModel):
    """Timestamped gait event with confidence and provenance."""

    event_id: str
    event_type: str  # "foot_strike" or "foot_off"
    side: str        # "left" or "right"
    frame_index: int
    timestamp_s: float
    confidence: float
    detection_method: str
    supporting_landmarks: List[str] = Field(default_factory=list)
    quality_status: str = "valid"


def detect_gait_events_from_poses(
    poses: List[FramePose],
    camera_view: str = "side",
    fps: float = 30.0,
) -> List[GaitEvent]:
    """
    Detect left and right foot strikes and foot offs from ankle/heel vertical velocity
    and trajectory extrema across video frames.
    """
    if len(poses) < int(fps * 0.8):
        return []

    timestamps = [p.timestamp_s for p in poses]
    frame_indices = [p.frame_index for p in poses]

    events: List[GaitEvent] = []

    for side in ["left", "right"]:
        ank_name = f"{side}_ankle"
        heel_name = f"{side}_heel"

        y_traj = []
        confs = []

        for p in poses:
            lm = p.landmarks
            if heel_name in lm and lm[heel_name].is_visible:
                y_traj.append(lm[heel_name].y_px)
                confs.append(lm[heel_name].confidence)
            elif ank_name in lm and lm[ank_name].is_visible:
                y_traj.append(lm[ank_name].y_px)
                confs.append(lm[ank_name].confidence)
            else:
                y_traj.append(np.nan)
                confs.append(0.0)

        y_arr = np.array(y_traj, dtype=np.float64)
        valid_mask = np.isfinite(y_arr)
        if valid_mask.sum() < len(poses) * 0.6:
            continue

        # Linear interpolation for filtering if small gaps exist
        x_all = np.arange(len(y_arr))
        interp_y = np.interp(x_all, x_all[valid_mask], y_arr[valid_mask])
        filt_y = butter_lowpass_filter(interp_y, cutoff_hz=4.0, fs_hz=fps)

        # In image coordinates, y increases downwards.
        # Highest vertical foot ground contact (foot strike) corresponds to local maxima in Y.
        min_dist = max(5, int(fps * 0.4))
        peaks_y, valleys_y = detect_extrema_events(filt_y, min_distance_frames=min_dist, prominence_factor=0.08)

        # Peaks in Y (lowest ground position) -> Foot Strike
        for p_idx in peaks_y:
            f_num = frame_indices[p_idx]
            t_s = timestamps[p_idx]
            c = float(confs[p_idx]) if p_idx < len(confs) else 0.7
            events.append(
                GaitEvent(
                    event_id=f"{side}_fs_{f_num}",
                    event_type="foot_strike",
                    side=side,
                    frame_index=f_num,
                    timestamp_s=round(t_s, 3),
                    confidence=round(max(0.5, c), 2),
                    detection_method="heel_vertical_extrema",
                    supporting_landmarks=[heel_name, ank_name],
                )
            )

        # Valleys in Y (toe-off upward lift initiation) -> Foot Off
        for v_idx in valleys_y:
            f_num = frame_indices[v_idx]
            t_s = timestamps[v_idx]
            c = float(confs[v_idx]) if v_idx < len(confs) else 0.7
            events.append(
                GaitEvent(
                    event_id=f"{side}_fo_{f_num}",
                    event_type="foot_off",
                    side=side,
                    frame_index=f_num,
                    timestamp_s=round(t_s, 3),
                    confidence=round(max(0.45, c), 2),
                    detection_method="foot_lift_extrema",
                    supporting_landmarks=[heel_name, ank_name],
                )
            )

    events.sort(key=lambda e: e.timestamp_s)
    return events
