"""Video-based biomechanical feature extraction with view-specific geometry and QC."""

from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from pydantic import BaseModel, Field

from src.gait_events.gait_cycle_segmenter import GaitCycle, normalize_cycle_trajectory
from src.pose_estimation.landmark_schema import FramePose


def compute_2d_angle(
    p_proximal: Tuple[float, float],
    p_vertex: Tuple[float, float],
    p_distal: Tuple[float, float],
) -> float:
    """
    Calculate 2D planar angle at vertex between proximal and distal segments (in degrees).
    """
    v1 = np.array([p_proximal[0] - p_vertex[0], p_proximal[1] - p_vertex[1]], dtype=np.float64)
    v2 = np.array([p_distal[0] - p_vertex[0], p_distal[1] - p_vertex[1]], dtype=np.float64)

    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)
    if norm1 < 1e-4 or norm2 < 1e-4:
        return 0.0

    cosine = np.clip(np.dot(v1, v2) / (norm1 * norm2), -1.0, 1.0)
    angle_rad = np.arccos(cosine)
    return float(np.degrees(angle_rad))


class VideoGaitFeature(BaseModel):
    """Standardized video-derived biomechanical measurement with quality control."""

    feature_name: str
    value: Optional[float] = None
    unit: str
    side: Optional[str] = None
    camera_view: str
    measurement_method: str
    quality_status: str  # "estimated", "measured", "low_confidence", "unavailable", "not_applicable"
    confidence: float
    cycle_count: int = 0
    cycle_consistency_sd: Optional[float] = None
    unavailability_reason: Optional[str] = None
    normalized_101_curve: Optional[List[float]] = None


def extract_video_features(
    poses: List[FramePose],
    cycles: List[GaitCycle],
    camera_view: str = "side",
) -> List[VideoGaitFeature]:
    """Extract view-supported features across segmented cycles."""
    features: List[VideoGaitFeature] = []

    complete_cycles = [c for c in cycles if c.is_complete]
    n_cycles = len(complete_cycles)

    # 1. Spatiotemporal features (cadence, cycle duration)
    if n_cycles > 0:
        durations = [c.duration_s for c in complete_cycles]
        mean_dur = float(np.mean(durations))
        sd_dur = float(np.std(durations, ddof=1)) if len(durations) > 1 else 0.0
        cadence_spm = (60.0 / mean_dur) * 2.0  # steps/min approx 2 steps per cycle

        features.append(
            VideoGaitFeature(
                feature_name="gait_cycle_duration",
                value=round(mean_dur, 3),
                unit="seconds",
                camera_view=camera_view,
                measurement_method="cycle_event_timestamps",
                quality_status="measured",
                confidence=0.85,
                cycle_count=n_cycles,
                cycle_consistency_sd=round(sd_dur, 3),
            )
        )
        features.append(
            VideoGaitFeature(
                feature_name="cadence",
                value=round(cadence_spm, 1),
                unit="steps/min",
                camera_view=camera_view,
                measurement_method="cycle_frequency_estimate",
                quality_status="estimated",
                confidence=0.80,
                cycle_count=n_cycles,
                cycle_consistency_sd=round(sd_dur, 3),
            )
        )
    else:
        features.append(
            VideoGaitFeature(
                feature_name="cadence",
                value=None,
                unit="steps/min",
                camera_view=camera_view,
                measurement_method="cycle_frequency_estimate",
                quality_status="unavailable",
                confidence=0.0,
                unavailability_reason="No complete gait cycles segmented",
            )
        )

    # 2. View-specific kinematic angles (Sagittal / Side view)
    if camera_view in {"side", "unknown"}:
        for side in ["left", "right"]:
            side_cycles = [c for c in complete_cycles if c.side == side]
            hip_k = f"{side}_hip"
            knee_k = f"{side}_knee"
            ank_k = f"{side}_ankle"

            # Check landmark visibility
            vis_counts = sum(
                1 for p in poses
                if hip_k in p.landmarks and knee_k in p.landmarks and ank_k in p.landmarks
                and p.landmarks[knee_k].is_visible
            )

            if vis_counts < len(poses) * 0.4:
                features.append(
                    VideoGaitFeature(
                        feature_name=f"{side}_knee_flexion_extension",
                        value=None,
                        unit="degrees",
                        side=side,
                        camera_view=camera_view,
                        measurement_method="2d_planar_joint_angle",
                        quality_status="unavailable",
                        confidence=0.0,
                        unavailability_reason=f"Insufficient visible {side} leg landmarks",
                    )
                )
                continue

            # Compute knee flexion angle across all frames (flexion = 180 - raw joint angle)
            angles_seq = []
            for p in poses:
                lm = p.landmarks
                if hip_k in lm and knee_k in lm and ank_k in lm:
                    raw_ang = compute_2d_angle(
                        (lm[hip_k].x_px, lm[hip_k].y_px),
                        (lm[knee_k].x_px, lm[knee_k].y_px),
                        (lm[ank_k].x_px, lm[ank_k].y_px),
                    )
                    flexion = max(0.0, 180.0 - raw_ang)
                    angles_seq.append(flexion)
                else:
                    angles_seq.append(np.nan)

            angles_arr = np.array(angles_seq)

            # Normalise across cycles if available
            norm_curves = []
            frame_map = {p.frame_index: idx for idx, p in enumerate(poses)}
            for cyc in side_cycles:
                if cyc.start_frame in frame_map and cyc.end_frame in frame_map:
                    s_idx = frame_map[cyc.start_frame]
                    e_idx = frame_map[cyc.end_frame]
                    seg = angles_arr[s_idx : e_idx + 1]
                    if np.isfinite(seg).sum() >= 2:
                        norm_curves.append(normalize_cycle_trajectory(seg, n_points=101))

            if norm_curves:
                mean_curve = np.nanmean(norm_curves, axis=0)
                mean_rom = float(np.nanmax(mean_curve) - np.nanmin(mean_curve))
                features.append(
                    VideoGaitFeature(
                        feature_name=f"{side}_knee_flexion_extension_rom",
                        value=round(mean_rom, 1),
                        unit="degrees",
                        side=side,
                        camera_view=camera_view,
                        measurement_method="2d_planar_joint_angle",
                        quality_status="estimated",
                        confidence=0.75,
                        cycle_count=len(norm_curves),
                        normalized_101_curve=[round(x, 2) for x in mean_curve.tolist()],
                    )
                )
            else:
                valid_ang = angles_arr[np.isfinite(angles_arr)]
                val = float(np.mean(valid_ang)) if valid_ang.size > 0 else None
                features.append(
                    VideoGaitFeature(
                        feature_name=f"{side}_knee_flexion_extension_rom",
                        value=round(val, 1) if val is not None else None,
                        unit="degrees",
                        side=side,
                        camera_view=camera_view,
                        measurement_method="2d_planar_joint_angle",
                        quality_status="low_confidence" if val is not None else "unavailable",
                        confidence=0.45 if val is not None else 0.0,
                        unavailability_reason="No complete cycle available for normalization",
                    )
                )

    # 3. Frontal view features (Knee alignment / Trunk lateral lean)
    if camera_view == "front":
        trunk_leans = []
        for p in poses:
            lm = p.landmarks
            if "left_shoulder" in lm and "right_shoulder" in lm and "left_hip" in lm and "right_hip" in lm:
                mid_sh_x = (lm["left_shoulder"].x_px + lm["right_shoulder"].x_px) / 2.0
                mid_hp_x = (lm["left_hip"].x_px + lm["right_hip"].x_px) / 2.0
                dx = mid_sh_x - mid_hp_x
                trunk_leans.append(abs(dx))

        if trunk_leans:
            features.append(
                VideoGaitFeature(
                    feature_name="trunk_lateral_displacement_px",
                    value=round(float(np.mean(trunk_leans)), 2),
                    unit="pixels",
                    camera_view=camera_view,
                    measurement_method="2d_coronal_trunk_offset",
                    quality_status="measured",
                    confidence=0.70,
                )
            )

    return features
