"""Metadata generation for trial_index.csv, subject_index.csv, and variable_dictionary.csv."""

from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd

from src.core.logging import get_logger
from src.data_loader.npz_discovery import EXPECTED_PARTICIPANTS
from src.data_loader.npz_validator import (
    ANGLE_BASES,
    COM_VARS,
    COP_VARS,
    GRF_VARS,
    MOMENT_VARS,
    POWER_VARS,
    ValidationReport,
)

logger = get_logger(__name__)

SOURCE_DOC = "Nature Scientific Data 2025 (s41597-025-06535-y) / Figshare 29300888.v1 / Plug-in Gait"


def generate_trial_index(report: ValidationReport, output_path: Path) -> Path:
    """Generate metadata/trial_index.csv from the validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in report.trial_results:
        rows.append(
            {
                "trial_id": r.trial_id,
                "participant_id": r.participant_id,
                "condition": r.condition_dir,
                "filename": r.filename,
                "gait_speed": r.gait_speed,
                "file_path": r.relative_path,
                "validation_status": r.validation_status,
                "has_kinematic_anomalies": r.has_kinematic_anomalies,
                "has_kinetic_anomalies": r.has_kinetic_anomalies,
            }
        )
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    logger.info("Generated trial index (%d rows) at %s", len(df), output_path)
    return output_path


def generate_subject_index(report: ValidationReport, output_path: Path) -> Path:
    """Generate metadata/subject_index.csv with participant-level summaries."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    by_subj: Dict[str, List] = {p: [] for p in sorted(EXPECTED_PARTICIPANTS)}
    for r in report.trial_results:
        by_subj.setdefault(r.participant_id, []).append(r)

    rows = []
    for subj in sorted(by_subj.keys()):
        trials = by_subj[subj]
        speeds = [t.gait_speed for t in trials if t.gait_speed is not None]
        conditions = sorted({t.condition_dir for t in trials})
        valid_count = sum(
            1 for t in trials if t.validation_status in {"valid", "valid_with_numeric_anomalies"}
        )
        invalid_count = sum(1 for t in trials if t.validation_status == "invalid")
        if len(trials) == 0:
            notes = "No NPZ files present; check data/raw/c3d/incomplete data or data/raw/txt/incomplete data"
            npz_avail = False
        else:
            notes = "Complete NPZ participant dataset"
            npz_avail = True

        rows.append(
            {
                "participant_id": subj,
                "npz_available": npz_avail,
                "total_trials": len(trials),
                "valid_or_usable_trials": valid_count,
                "invalid_trials": invalid_count,
                "conditions_count": len(conditions),
                "conditions": ";".join(conditions),
                "mean_gait_speed_mps": round(sum(speeds) / len(speeds), 4) if speeds else None,
                "min_gait_speed_mps": round(min(speeds), 4) if speeds else None,
                "max_gait_speed_mps": round(max(speeds), 4) if speeds else None,
                "notes": notes,
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    logger.info("Generated subject index (%d rows) at %s", len(df), output_path)
    return output_path


def _axis_info(var_name: str) -> Tuple[str, str]:
    base = var_name.replace("_contra", "")
    if base.endswith(("x", "x1", "x2")):
        return "X", "Sagittal plane"
    if base.endswith(("y", "y1", "y2")):
        return "Y", "Frontal plane"
    if base.endswith(("z", "z1", "z2")):
        return "Z", "Transverse plane"
    return "N/A", "N/A"


def generate_variable_dictionary(output_path: Path) -> Path:
    """Generate metadata/variable_dictionary.csv for all 79 NPZ variables."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    entries = []

    # Metadata scalars
    entries.extend([
        {
            "variable_name": "prob",
            "description": "Participant identifier string",
            "variable_category": "metadata",
            "axis": "N/A",
            "units": "dimensionless",
            "data_type": "string",
            "shape": "()",
            "interpretation": "Subject ID (Ref01-Ref13)",
            "source_documentation": SOURCE_DOC,
            "sign_convention_status": "not_applicable",
        },
        {
            "variable_name": "folder",
            "description": "Walking condition folder label",
            "variable_category": "metadata",
            "axis": "N/A",
            "units": "dimensionless",
            "data_type": "string",
            "shape": "()",
            "interpretation": "Terrain and direction condition",
            "source_documentation": SOURCE_DOC,
            "sign_convention_status": "not_applicable",
        },
        {
            "variable_name": "gait_speed",
            "description": "Walking speed for the trial",
            "variable_category": "metadata",
            "axis": "N/A",
            "units": "m/s",
            "data_type": "float64",
            "shape": "()",
            "interpretation": "Mean forward progression speed",
            "source_documentation": SOURCE_DOC,
            "sign_convention_status": "positive_forward",
        },
    ])

    # Joint angles
    for var in ANGLE_BASES:
        axis, plane = _axis_info(var)
        is_contra = var.endswith("_contra")
        joint = var.replace("_contra", "")[:-2]
        side_note = "contralateral side" if is_contra else "ipsilateral/primary side"

        if joint == "knee" and axis == "X":
            interp = f"Knee flexion/extension ({side_note}); positive = flexion"
            sign_status = "verified_positive_flexion"
        elif axis == "X":
            interp = f"{joint.capitalize()} sagittal-plane angle ({side_note})"
            sign_status = "unverified_positive_direction"
        else:
            interp = f"{joint.capitalize()} {plane.lower()} angle ({side_note})"
            sign_status = "unverified_positive_direction"

        entries.append(
            {
                "variable_name": var,
                "description": f"Plug-in Gait {joint} joint angle ({plane}, {side_note})",
                "variable_category": "joint_angle",
                "axis": axis,
                "units": "degrees",
                "data_type": "float64",
                "shape": "(101,)",
                "interpretation": interp,
                "source_documentation": SOURCE_DOC,
                "sign_convention_status": sign_status,
            }
        )

    # Joint moments
    for var in MOMENT_VARS:
        axis, plane = _axis_info(var)
        joint = var[:-2]
        entries.append(
            {
                "variable_name": var,
                "description": f"Plug-in Gait {joint} joint moment ({plane})",
                "variable_category": "joint_moment",
                "axis": axis,
                "units": "Nm/kg (see original dataset documentation)",
                "data_type": "float64",
                "shape": "(101,)",
                "interpretation": f"{joint.capitalize()} internal/external moment along {axis}-axis",
                "source_documentation": SOURCE_DOC,
                "sign_convention_status": "unverified_positive_direction",
            }
        )

    # Joint powers
    for var in POWER_VARS:
        axis, plane = _axis_info(var)
        joint = var[:-2]
        entries.append(
            {
                "variable_name": var,
                "description": f"Plug-in Gait {joint} joint power ({plane})",
                "variable_category": "joint_power",
                "axis": axis,
                "units": "W/kg (see original dataset documentation)",
                "data_type": "float64",
                "shape": "(101,)",
                "interpretation": f"{joint.capitalize()} joint power component along {axis}-axis",
                "source_documentation": SOURCE_DOC,
                "sign_convention_status": "unverified_positive_direction",
            }
        )

    # GRF, CoP, CoM
    for var in GRF_VARS:
        axis, _ = _axis_info(var)
        plate = var[-1]
        entries.append(
            {
                "variable_name": var,
                "description": f"Ground reaction force plate {plate} ({axis}-axis)",
                "variable_category": "ground_reaction_force",
                "axis": axis,
                "units": "N or N/kg (see original dataset documentation)",
                "data_type": "float64",
                "shape": "(101,)",
                "interpretation": f"GRF component along {axis} for contact {plate}",
                "source_documentation": SOURCE_DOC,
                "sign_convention_status": "unverified_positive_direction",
            }
        )

    for var in COP_VARS:
        axis, _ = _axis_info(var)
        plate = var[-1]
        entries.append(
            {
                "variable_name": var,
                "description": f"Centre of pressure plate {plate} ({axis}-axis)",
                "variable_category": "centre_of_pressure",
                "axis": axis,
                "units": "m or mm (see original dataset documentation)",
                "data_type": "float64",
                "shape": "(101,)",
                "interpretation": f"CoP coordinate along {axis} for contact {plate}",
                "source_documentation": SOURCE_DOC,
                "sign_convention_status": "unverified_positive_direction",
            }
        )

    for var in COM_VARS:
        axis, _ = _axis_info(var)
        plate = var[-1]
        entries.append(
            {
                "variable_name": var,
                "description": f"Centre of mass trajectory {plate} ({axis}-axis)",
                "variable_category": "centre_of_mass",
                "axis": axis,
                "units": "m or mm (see original dataset documentation)",
                "data_type": "float64",
                "shape": "(101,)",
                "interpretation": f"CoM coordinate along {axis} for cycle {plate}",
                "source_documentation": SOURCE_DOC,
                "sign_convention_status": "unverified_positive_direction",
            }
        )

    # VPP and R2
    for idx in ("1", "2"):
        entries.append(
            {
                "variable_name": f"VPP{idx}",
                "description": f"Virtual Pivot Point coordinates for contact {idx}",
                "variable_category": "vpp_model",
                "axis": "2D (horizontal, vertical)",
                "units": "m",
                "data_type": "float64",
                "shape": "(2,)",
                "interpretation": "Virtual Pivot Point relative to CoM",
                "source_documentation": SOURCE_DOC,
                "sign_convention_status": "see_source_paper",
            }
        )
        entries.append(
            {
                "variable_name": f"R2_{idx}",
                "description": f"VPP model coefficient of determination for contact {idx}",
                "variable_category": "vpp_model",
                "axis": "N/A",
                "units": "dimensionless",
                "data_type": "float64",
                "shape": "()",
                "interpretation": "Goodness-of-fit R^2 (0 to 1)",
                "source_documentation": SOURCE_DOC,
                "sign_convention_status": "not_applicable",
            }
        )

    df = pd.DataFrame(entries)
    df.to_csv(output_path, index=False)
    logger.info("Generated variable dictionary (%d variables) at %s", len(df), output_path)
    return output_path
