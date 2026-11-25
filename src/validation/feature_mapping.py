"""Specification and evaluation of feature compatibility between video and NPZ reference."""

from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

from src.validation.validation_schema import FeatureCompatibilityDefinition

COMPATIBILITY_DEFINITIONS: List[FeatureCompatibilityDefinition] = [
    FeatureCompatibilityDefinition(
        feature_name="left_knee_flexion_extension_rom",
        reference_var="kneeAx",
        anatomical_definition="Left knee sagittal-plane range of motion across gait cycle",
        movement_plane="sagittal",
        video_units="degrees",
        reference_units="degrees",
        units_compatible=True,
        required_camera_view="side",
        positive_direction_meaning="Flexion",
        negative_direction_meaning="Extension",
        compatibility_status="conditionally_comparable",
        calibration_required=False,
        known_limitations=[
            "2D planar angle projected onto camera sensor plane; sensitive to camera perspective alignment.",
            "Plug-in Gait 3D kinematics computes Cardan joint angles from 3D marker triads; video computes 2D vertex angle.",
            "Valid only under true sagittal/side view perpendicular to walking direction.",
        ],
    ),
    FeatureCompatibilityDefinition(
        feature_name="right_knee_flexion_extension_rom",
        reference_var="kneeAx_contra",
        anatomical_definition="Right knee sagittal-plane range of motion across gait cycle",
        movement_plane="sagittal",
        video_units="degrees",
        reference_units="degrees",
        units_compatible=True,
        required_camera_view="side",
        positive_direction_meaning="Flexion",
        negative_direction_meaning="Extension",
        compatibility_status="conditionally_comparable",
        calibration_required=False,
        known_limitations=[
            "2D planar angle projected onto camera sensor plane; sensitive to camera perspective alignment.",
            "Reference kneeAx_contra mapping to anatomical right knee requires confirmation per subject.",
            "Contralateral limb in video side view suffers from self-occlusion during stance/swing overlap.",
        ],
    ),
    FeatureCompatibilityDefinition(
        feature_name="cadence",
        reference_var="gait_speed",
        anatomical_definition="Walking step cadence vs progression speed",
        movement_plane="spatiotemporal",
        video_units="steps/min",
        reference_units="m/s",
        units_compatible=False,
        required_camera_view="any",
        positive_direction_meaning="Increasing cadence",
        negative_direction_meaning="N/A",
        compatibility_status="not_comparable",
        calibration_required=False,
        known_limitations=[
            "Unit and physical concept mismatch: video estimates cadence (steps/min), NPZ supplies speed (m/s).",
            "Speed requires physical metric spatial calibration not established from monocular video without calibrated scale.",
        ],
    ),
    FeatureCompatibilityDefinition(
        feature_name="trunk_lateral_displacement_px",
        reference_var="thoraxAy",
        anatomical_definition="Coronal plane trunk lateral lean / displacement",
        movement_plane="frontal",
        video_units="pixels",
        reference_units="degrees",
        units_compatible=False,
        required_camera_view="front",
        positive_direction_meaning="Rightward lateral tilt",
        negative_direction_meaning="Leftward lateral tilt",
        compatibility_status="not_comparable",
        calibration_required=True,
        known_limitations=[
            "Unit mismatch: video outputs uncalibrated pixels, reference outputs 3D angular degrees.",
            "Pixel distance varies with subject distance from camera.",
        ],
    ),
    FeatureCompatibilityDefinition(
        feature_name="ankle_angle_planar",
        reference_var="ankleAx",
        anatomical_definition="Ankle sagittal angle (dorsi/plantarflexion)",
        movement_plane="sagittal",
        video_units="degrees",
        reference_units="degrees",
        units_compatible=True,
        required_camera_view="side",
        positive_direction_meaning="Dorsiflexion (needs verification)",
        negative_direction_meaning="Plantarflexion",
        compatibility_status="conditionally_comparable",
        calibration_required=False,
        known_limitations=[
            "Video pose estimators lack rigid calcaneus/metatarsal landmarks (approximate heel/toe), causing high foot angle noise.",
            "Ankle coordinate offset and zero baseline differ significantly between 2D video heuristics and PiG static calibration.",
        ],
    ),
]


def get_compatibility_definition(feature_name: str) -> Optional[FeatureCompatibilityDefinition]:
    """Retrieve compatibility specification for a video feature."""
    for defn in COMPATIBILITY_DEFINITIONS:
        if defn.feature_name == feature_name:
            return defn
    return None


def export_compatibility_matrix(output_path: Path) -> Path:
    """Export feature compatibility matrix to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for d in COMPATIBILITY_DEFINITIONS:
        rows.append(
            {
                "feature_name": d.feature_name,
                "reference_var": d.reference_var,
                "movement_plane": d.movement_plane,
                "video_units": d.video_units,
                "reference_units": d.reference_units,
                "units_compatible": d.units_compatible,
                "required_camera_view": d.required_camera_view,
                "compatibility_status": d.compatibility_status,
                "calibration_required": d.calibration_required,
                "known_limitations": " | ".join(d.known_limitations),
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    return output_path
