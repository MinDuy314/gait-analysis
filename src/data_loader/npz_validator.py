"""Schema validation and quality control for NPZ motion-capture trials."""

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from src.core.logging import get_logger
from src.data_loader.npz_discovery import DiscoveredNPZFile

logger = get_logger(__name__)

# Canonical 79-variable schema
METADATA_SCALARS: Set[str] = {"prob", "folder", "gait_speed"}
OTHER_SCALARS: Set[str] = {"R2_1", "R2_2"}
VECTOR_2_VARS: Set[str] = {"VPP1", "VPP2"}

ANGLE_BASES: List[str] = [
    "ankleAx", "ankleAy", "ankleAz",
    "ankleAx_contra", "ankleAy_contra", "ankleAz_contra",
    "kneeAx", "kneeAy", "kneeAz",
    "kneeAx_contra", "kneeAy_contra", "kneeAz_contra",
    "hipAx", "hipAy", "hipAz",
    "hipAx_contra", "hipAy_contra", "hipAz_contra",
    "shoulderAx", "shoulderAy", "shoulderAz",
    "shoulderAx_contra", "shoulderAy_contra", "shoulderAz_contra",
    "elbowAx", "elbowAy", "elbowAz",
    "elbowAx_contra", "elbowAy_contra", "elbowAz_contra",
    "headAx", "headAy", "headAz",
    "thoraxAx", "thoraxAy", "thoraxAz",
]

MOMENT_VARS: List[str] = [
    "ankleMx", "ankleMy", "ankleMz",
    "kneeMx", "kneeMy", "kneeMz",
    "hipMx", "hipMy", "hipMz",
]

POWER_VARS: List[str] = [
    "anklePx", "anklePy", "anklePz",
    "kneePx", "kneePy", "kneePz",
    "hipPx", "hipPy", "hipPz",
]

GRF_VARS: List[str] = ["GRFx1", "GRFx2", "GRFy1", "GRFy2", "GRFz1", "GRFz2"]
COP_VARS: List[str] = ["CoPx1", "CoPx2", "CoPy1", "CoPy2", "CoPz1", "CoPz2"]
COM_VARS: List[str] = ["CoMx1", "CoMx2", "CoMy1", "CoMy2", "CoMz1", "CoMz2"]

CURVE_101_VARS: Set[str] = set(ANGLE_BASES + MOMENT_VARS + POWER_VARS + GRF_VARS + COP_VARS + COM_VARS)
EXPECTED_VARIABLES: Set[str] = METADATA_SCALARS | OTHER_SCALARS | VECTOR_2_VARS | CURVE_101_VARS

REQUIRED_KNEE_VARS: Set[str] = {
    "kneeAx", "kneeAy", "kneeAz",
    "kneeAx_contra", "kneeAy_contra", "kneeAz_contra",
}


class NumericAnomaly(BaseModel):
    """Represents a NaN or Inf anomaly detected in a variable."""

    trial_id: str
    participant_id: str
    condition: str
    variable_name: str
    anomaly_type: str  # "nan", "inf", "nan_and_inf"
    nan_count: int = 0
    inf_count: int = 0
    total_elements: int = 0
    category: str  # "kinematics", "kinetics", "other"


class TrialValidationResult(BaseModel):
    """Validation outcome for a single NPZ file."""

    trial_id: str
    participant_id: str
    condition_dir: str
    filename: str
    relative_path: str
    validation_status: str  # "valid", "valid_with_numeric_anomalies", "invalid"
    load_error: Optional[str] = None
    prob_metadata: Optional[str] = None
    folder_metadata: Optional[str] = None
    gait_speed: Optional[float] = None
    variable_count: int = 0
    missing_variables: List[str] = Field(default_factory=list)
    unexpected_variables: List[str] = Field(default_factory=list)
    missing_knee_variables: List[str] = Field(default_factory=list)
    shape_inconsistencies: List[str] = Field(default_factory=list)
    dtype_inconsistencies: List[str] = Field(default_factory=list)
    numeric_anomalies: List[NumericAnomaly] = Field(default_factory=list)
    has_kinematic_anomalies: bool = False
    has_kinetic_anomalies: bool = False


class ValidationReport(BaseModel):
    """Dataset-wide NPZ validation summary."""

    total_files_discovered: int
    valid_files: int
    valid_with_numeric_anomalies: int
    invalid_files: int
    total_missing_variables_events: int
    total_shape_inconsistencies: int
    total_numeric_anomaly_records: int
    participant_distribution: Dict[str, int]
    condition_distribution: Dict[str, int]
    trial_results: List[TrialValidationResult] = Field(default_factory=list)


def _classify_var_category(var_name: str) -> str:
    if var_name in ANGLE_BASES:
        return "kinematics"
    if var_name in MOMENT_VARS or var_name in POWER_VARS or var_name in GRF_VARS or var_name in COP_VARS:
        return "kinetics"
    return "other"


def validate_npz_trial(
    file_info: DiscoveredNPZFile,
    gait_cycle_points: int = 101,
) -> TrialValidationResult:
    """Validate a single NPZ file against the 79-variable schema."""
    path = Path(file_info.absolute_path)
    missing_vars: List[str] = []
    unexpected_vars: List[str] = []
    missing_knee: List[str] = []
    shape_issues: List[str] = []
    dtype_issues: List[str] = []
    anomalies: List[NumericAnomaly] = []

    prob_val: Optional[str] = None
    folder_val: Optional[str] = None
    gait_speed_val: Optional[float] = None

    try:
        with np.load(path, allow_pickle=True) as data:
            keys = set(data.keys())
            var_count = len(keys)
            missing_vars = sorted(EXPECTED_VARIABLES - keys)
            unexpected_vars = sorted(keys - EXPECTED_VARIABLES)
            missing_knee = sorted(REQUIRED_KNEE_VARS - keys)

            for k in sorted(keys):
                arr = data[k]
                # Metadata extraction
                if k == "prob":
                    prob_val = str(arr.item()) if arr.ndim == 0 else str(arr)
                elif k == "folder":
                    folder_val = str(arr.item()) if arr.ndim == 0 else str(arr)
                elif k == "gait_speed":
                    if arr.ndim == 0 and np.issubdtype(arr.dtype, np.number):
                        val = float(arr.item())
                        gait_speed_val = None if (np.isnan(val) or np.isinf(val)) else val

                # Shape validation
                if k in CURVE_101_VARS:
                    if arr.shape != (gait_cycle_points,):
                        shape_issues.append(f"{k}: expected ({gait_cycle_points},), got {arr.shape}")
                elif k in VECTOR_2_VARS:
                    if arr.shape != (2,):
                        shape_issues.append(f"{k}: expected (2,), got {arr.shape}")
                elif k in METADATA_SCALARS or k in OTHER_SCALARS:
                    if arr.shape != ():
                        shape_issues.append(f"{k}: expected (), got {arr.shape}")

                # Dtype validation
                if k in {"prob", "folder"}:
                    if not (np.issubdtype(arr.dtype, np.str_) or np.issubdtype(arr.dtype, np.bytes_) or arr.dtype == object):
                        dtype_issues.append(f"{k}: expected string dtype, got {arr.dtype}")
                elif k in EXPECTED_VARIABLES:
                    if not np.issubdtype(arr.dtype, np.number):
                        dtype_issues.append(f"{k}: expected numeric dtype, got {arr.dtype}")
                    else:
                        nan_cnt = int(np.isnan(arr).sum())
                        inf_cnt = int(np.isinf(arr).sum())
                        if nan_cnt > 0 or inf_cnt > 0:
                            if nan_cnt > 0 and inf_cnt > 0:
                                a_type = "nan_and_inf"
                            elif nan_cnt > 0:
                                a_type = "nan"
                            else:
                                a_type = "inf"
                            anomalies.append(
                                NumericAnomaly(
                                    trial_id=file_info.trial_id,
                                    participant_id=file_info.participant_id,
                                    condition=file_info.condition_dir,
                                    variable_name=k,
                                    anomaly_type=a_type,
                                    nan_count=nan_cnt,
                                    inf_count=inf_cnt,
                                    total_elements=int(arr.size),
                                    category=_classify_var_category(k),
                                )
                            )

    except Exception as exc:
        return TrialValidationResult(
            trial_id=file_info.trial_id,
            participant_id=file_info.participant_id,
            condition_dir=file_info.condition_dir,
            filename=file_info.filename,
            relative_path=file_info.relative_path,
            validation_status="invalid",
            load_error=str(exc),
        )

    has_kin_anom = any(a.category == "kinematics" for a in anomalies)
    has_kinet_anom = any(a.category == "kinetics" for a in anomalies)

    if missing_vars or unexpected_vars or missing_knee or shape_issues or dtype_issues:
        status = "invalid"
    elif anomalies:
        status = "valid_with_numeric_anomalies"
    else:
        status = "valid"

    return TrialValidationResult(
        trial_id=file_info.trial_id,
        participant_id=file_info.participant_id,
        condition_dir=file_info.condition_dir,
        filename=file_info.filename,
        relative_path=file_info.relative_path,
        validation_status=status,
        prob_metadata=prob_val,
        folder_metadata=folder_val,
        gait_speed=gait_speed_val,
        variable_count=var_count,
        missing_variables=missing_vars,
        unexpected_variables=unexpected_vars,
        missing_knee_variables=missing_knee,
        shape_inconsistencies=shape_issues,
        dtype_inconsistencies=dtype_issues,
        numeric_anomalies=anomalies,
        has_kinematic_anomalies=has_kin_anom,
        has_kinetic_anomalies=has_kinet_anom,
    )


def validate_all_npz(
    files: List[DiscoveredNPZFile],
    gait_cycle_points: int = 101,
) -> ValidationReport:
    """Validate all discovered NPZ trials and compile a dataset-wide report."""
    results: List[TrialValidationResult] = []
    part_dist: Counter = Counter()
    cond_dist: Counter = Counter()

    for f in files:
        res = validate_npz_trial(f, gait_cycle_points=gait_cycle_points)
        results.append(res)
        part_dist[res.participant_id] += 1
        cond_dist[res.condition_dir] += 1

    valid_cnt = sum(1 for r in results if r.validation_status == "valid")
    anom_cnt = sum(1 for r in results if r.validation_status == "valid_with_numeric_anomalies")
    invalid_cnt = sum(1 for r in results if r.validation_status == "invalid")
    missing_var_events = sum(len(r.missing_variables) for r in results)
    shape_inc_cnt = sum(len(r.shape_inconsistencies) for r in results)
    num_anom_cnt = sum(len(r.numeric_anomalies) for r in results)

    logger.info(
        "NPZ validation complete: total=%d, valid=%d, valid_with_anomalies=%d, invalid=%d",
        len(results),
        valid_cnt,
        anom_cnt,
        invalid_cnt,
    )

    return ValidationReport(
        total_files_discovered=len(results),
        valid_files=valid_cnt,
        valid_with_numeric_anomalies=anom_cnt,
        invalid_files=invalid_cnt,
        total_missing_variables_events=missing_var_events,
        total_shape_inconsistencies=shape_inc_cnt,
        total_numeric_anomaly_records=num_anom_cnt,
        participant_distribution=dict(sorted(part_dist.items())),
        condition_distribution=dict(sorted(cond_dist.items())),
        trial_results=results,
    )


def write_qc_reports(report: ValidationReport, qc_dir: Path) -> Tuple[Path, Path, Path]:
    """Write QC summary, missing data, and invalid trials CSV reports."""
    qc_dir.mkdir(parents=True, exist_ok=True)

    # 1. qc_summary.csv
    summary_rows = [
        {"metric": "total_files_discovered", "value": report.total_files_discovered},
        {"metric": "valid_files", "value": report.valid_files},
        {"metric": "valid_with_numeric_anomalies", "value": report.valid_with_numeric_anomalies},
        {"metric": "invalid_files", "value": report.invalid_files},
        {"metric": "total_missing_variables_events", "value": report.total_missing_variables_events},
        {"metric": "total_shape_inconsistencies", "value": report.total_shape_inconsistencies},
        {"metric": "total_numeric_anomaly_records", "value": report.total_numeric_anomaly_records},
    ]
    for p, cnt in report.participant_distribution.items():
        summary_rows.append({"metric": f"participant_count_{p}", "value": cnt})
    for c, cnt in report.condition_distribution.items():
        summary_rows.append({"metric": f"condition_count_{c}", "value": cnt})

    summary_path = qc_dir / "qc_summary.csv"
    pd.DataFrame(summary_rows).to_csv(summary_path, index=False)

    # 2. missing_data.csv (all NaN/Inf and missing variable events)
    missing_rows = []
    for r in report.trial_results:
        for mv in r.missing_variables:
            missing_rows.append(
                {
                    "trial_id": r.trial_id,
                    "participant_id": r.participant_id,
                    "condition": r.condition_dir,
                    "variable_name": mv,
                    "issue_type": "missing_variable",
                    "nan_count": 0,
                    "inf_count": 0,
                    "total_elements": 0,
                    "category": _classify_var_category(mv),
                }
            )
        for anom in r.numeric_anomalies:
            missing_rows.append(
                {
                    "trial_id": anom.trial_id,
                    "participant_id": anom.participant_id,
                    "condition": anom.condition,
                    "variable_name": anom.variable_name,
                    "issue_type": anom.anomaly_type,
                    "nan_count": anom.nan_count,
                    "inf_count": anom.inf_count,
                    "total_elements": anom.total_elements,
                    "category": anom.category,
                }
            )
    missing_path = qc_dir / "missing_data.csv"
    missing_cols = [
        "trial_id", "participant_id", "condition", "variable_name",
        "issue_type", "nan_count", "inf_count", "total_elements", "category",
    ]
    pd.DataFrame(missing_rows, columns=missing_cols).to_csv(missing_path, index=False)

    # 3. invalid_trials.csv
    invalid_rows = []
    for r in report.trial_results:
        if r.validation_status == "invalid" or r.has_kinematic_anomalies:
            invalid_rows.append(
                {
                    "trial_id": r.trial_id,
                    "participant_id": r.participant_id,
                    "condition": r.condition_dir,
                    "filename": r.filename,
                    "validation_status": r.validation_status,
                    "load_error": r.load_error or "",
                    "missing_variables": ";".join(r.missing_variables),
                    "unexpected_variables": ";".join(r.unexpected_variables),
                    "shape_inconsistencies": ";".join(r.shape_inconsistencies),
                    "dtype_inconsistencies": ";".join(r.dtype_inconsistencies),
                    "has_kinematic_anomalies": r.has_kinematic_anomalies,
                }
            )
    invalid_path = qc_dir / "invalid_trials.csv"
    invalid_cols = [
        "trial_id", "participant_id", "condition", "filename", "validation_status",
        "load_error", "missing_variables", "unexpected_variables",
        "shape_inconsistencies", "dtype_inconsistencies", "has_kinematic_anomalies",
    ]
    pd.DataFrame(invalid_rows, columns=invalid_cols).to_csv(invalid_path, index=False)

    logger.info("Wrote QC reports to %s", qc_dir)
    return summary_path, missing_path, invalid_path
