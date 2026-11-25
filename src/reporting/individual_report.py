from datetime import datetime
from typing import Any, Dict, Optional
from src.assessment.assessment_schema import GaitAssessment
from src.progress.progress_schema import ProgressReport
from src.reporting.report_schema import GaitReport, ReportType


def generate_individual_report(
    assessment: GaitAssessment,
    progress: Optional[ProgressReport] = None,
    session_summary: Optional[Dict[str, Any]] = None,
) -> GaitReport:
    lines = [
        "# Gait Analysis Summary",
        f"\n*Session: {assessment.context.session_id} | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*",
        "\n---",
        "\n## Recording Quality",
    ]

    view = assessment.context.camera_view or "not specified"
    cal = assessment.context.calibration_status or "not specified"
    lines.append(f"- Camera view: **{view}**")
    lines.append(f"- Calibration: **{cal}**")
    lines.append(f"- Overall assessment confidence: **{assessment.overall_status.value}**")

    lines.append("\n## What Was Measured")
    if assessment.feature_interpretations:
        for interp in assessment.feature_interpretations:
            status_icon = {
                "supported": "\u2713",
                "limited_evidence": "\u26a0",
                "insufficient_data": "\u25cb",
                "not_assessable": "\u2717",
            }.get(interp.status.value, "?")
            lines.append(f"- {status_icon} **{interp.feature_name}**: {interp.interpretation_text}")
    else:
        lines.append("- No features were assessable from this recording.")

    if assessment.bilateral_results:
        lines.append("\n## Left-Right Comparison")
        for b in assessment.bilateral_results:
            lines.append(f"- **{b.feature_name}**: {b.interpretation}")
            if b.limitations:
                lines.append(f"  - *Note: {b.limitations[0]}*")

    if progress:
        lines.append("\n## Progress Compared to Your Baseline")
        improved = [fc for fc in progress.feature_changes if fc.category.value == "improvement"]
        deteriorated = [fc for fc in progress.feature_changes if fc.category.value == "deterioration"]
        unchanged = [fc for fc in progress.feature_changes if fc.category.value == "no_meaningful_change"]
        lines.append(f"- {len(improved)} feature(s) show improvement trends.")
        lines.append(f"- {len(deteriorated)} feature(s) show deterioration trends.")
        lines.append(f"- {len(unchanged)} feature(s) show no meaningful change.")
        if progress.comparability_issues:
            lines.append(f"\n*Comparison note: {progress.comparability_issues[0]}*")

    lines.append("\n## Limitations and Important Notes")
    for lim in assessment.global_limitations:
        lines.append(f"- {lim}")
    lines.append(
        "\n*This report is generated from video analysis only. It is not a clinical assessment. "
        "Please consult a qualified healthcare professional for clinical interpretation.*"
    )

    content = "\n".join(lines)
    return GaitReport(
        report_type=ReportType.individual,
        subject_id=assessment.context.subject_id,
        session_id=assessment.context.session_id,
        assessment_id=assessment.assessment_id,
        content_md=content,
        limitations=assessment.global_limitations,
        provenance={
            "pose_model": assessment.context.pose_model,
            "pose_model_version": assessment.context.pose_model_version,
            "assessment_rule_version": assessment.context.assessment_rule_version,
        },
    )
