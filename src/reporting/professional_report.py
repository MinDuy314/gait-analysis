"""Clinical gait rehabilitation report generator."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from src.assessment.assessment_schema import GaitAssessment
from src.progress.progress_schema import ProgressReport
from src.reporting.report_schema import GaitReport, ReportType


def _fmt_num(val: Optional[float], unit: str, decimals: int = 2) -> str:
    if val is None:
        return "Unavailable"
    return f"{val:.{decimals}f} {unit}".strip()


def _fmt_delta(val: Optional[float], pct: Optional[float], unit: str, decimals: int = 2) -> str:
    if val is None:
        return "Unavailable"
    pct_str = f" ({pct:+.1f}%)" if pct is not None else ""
    return f"{val:+.{decimals}f} {unit}{pct_str}".strip()


def generate_professional_report(
    assessment: GaitAssessment,
    progress: Optional[ProgressReport] = None,
    session_summary: Optional[Dict[str, Any]] = None,
    longitudinal: Optional[Dict[str, Any]] = None,
    clinician_name: Optional[str] = None,
    clinician_notes: Optional[str] = None,
    rehabilitation_priorities: Optional[List[str]] = None,
    recommendations: Optional[str] = None,
) -> GaitReport:
    ctx = assessment.context
    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    ws = (longitudinal or {}).get("walking_speed") or {}
    cad = (longitudinal or {}).get("cadence") or {}
    period_start = (longitudinal or {}).get("period_start")
    period_end = (longitudinal or {}).get("period_end")
    period_str = f"{period_start[:10]} to {period_end[:10]}" if period_start and period_end else "Single session"

    lines = [
        "# Professional Gait Analysis Report",
        f"\n*Session: {ctx.session_id} | Generated: {now_str}*",
        "\n---",
        "\n## 1. Patient and Assessment Information (Session Context)",
        "| Parameter | Value |",
        "|-----------|-------|",
        f"| Subject ID | {ctx.subject_id} |",
        f"| Assessment Date | {assessment.created_at.strftime('%Y-%m-%d') if assessment.created_at else now_str} |",
        f"| Assessing Clinician | {clinician_name or 'Pending clinician review'} |",
        f"| Comparison Period | {period_str} |",
        f"| Camera View | {ctx.camera_view or 'not specified'} |",
        f"| Calibration | {ctx.calibration_status or 'not specified'} |",
        f"| Walking Speed (Session) | {_fmt_num(ctx.walking_speed_ms, 'm/s')} |",
        f"| Surface / Footwear | {ctx.walking_surface or 'not specified'} / {ctx.footwear or 'not specified'} |",
        f"| Pose Model | {ctx.pose_model} v{ctx.pose_model_version} |",
    ]

    ws_pct_str = f"{ws['percentage_change']:+.1f}%" if ws.get("percentage_change") is not None else "Unavailable"
    cad_pct_str = f"{cad['percentage_change']:+.1f}%" if cad.get("percentage_change") is not None else "Unavailable"

    # Section 2: Measurement Summary
    lines.extend([
        "\n## 2. Measurement Summary",
        f"\nOverall Assessment Status: **{assessment.overall_status.value}**\n",
        "| Metric | Baseline | Current / Latest | Absolute Change | % Change | Trend | Valid Sessions |",
        "|--------|----------|------------------|-----------------|----------|-------|----------------|",
        f"| Walking Speed | {_fmt_num(ws.get('baseline_value'), 'm/s')} | {_fmt_num(ws.get('latest_value'), 'm/s')} | {_fmt_delta(ws.get('absolute_change'), None, 'm/s')} | {ws_pct_str} | {ws.get('trend', 'insufficient_data')} | {ws.get('valid_count', 0)} |",
        f"| Cadence | {_fmt_num(cad.get('baseline_value'), 'steps/min', 1)} | {_fmt_num(cad.get('latest_value'), 'steps/min', 1)} | {_fmt_delta(cad.get('absolute_change'), None, 'steps/min', 1)} | {cad_pct_str} | {cad.get('trend', 'insufficient_data')} | {cad.get('valid_count', 0)} |",
    ])

    if assessment.feature_interpretations:
        lines.append("\n### Session Biomechanical Measurements")
        for interp in assessment.feature_interpretations:
            val_str = f"{interp.value:.2f} {interp.unit}" if interp.value is not None else "Unavailable"
            lines.append(f"- **{interp.feature_name}**: {val_str} (status: `{interp.status.value}`, confidence: {interp.confidence:.2f})")

    # Section 3: Clinical Interpretation
    lines.append("\n## 3. Clinical Interpretation")
    ws_interp = {
        "metric": "Walking Speed (m/s)",
        "what_it_represents": "Overall functional ambulation velocity across the captured walking bout.",
        "current_indication": (
            f"Latest valid walking speed is {ws['latest_value']:.2f} m/s."
            if ws.get("latest_value") is not None
            else "Current walking speed could not be reliably determined (uncalibrated 2D view or missing timed speed)."
        ),
        "change_over_time": ws.get("trend_explanation") or "Insufficient longitudinal data to evaluate change.",
        "trend": ws.get("trend", "insufficient_data"),
        "requires_further_assessment": ws.get("trend") in ("declined", "insufficient_data") or ws.get("latest_value") is None,
    }
    cad_interp = {
        "metric": "Cadence (steps/min)",
        "what_it_represents": "Step frequency per minute during steady walking.",
        "current_indication": (
            f"Latest valid cadence is {cad['latest_value']:.1f} steps/min."
            if cad.get("latest_value") is not None
            else "Current cadence could not be reliably determined from the available video."
        ),
        "change_over_time": cad.get("trend_explanation") or "Insufficient longitudinal data to evaluate change.",
        "trend": cad.get("trend", "insufficient_data"),
        "requires_further_assessment": cad.get("trend") in ("declined", "insufficient_data") or cad.get("latest_value") is None,
    }
    for ci in (ws_interp, cad_interp):
        lines.append(f"\n### {ci['metric']}")
        lines.append(f"- **Meaning:** {ci['what_it_represents']}")
        lines.append(f"- **Current Status:** {ci['current_indication']}")
        lines.append(f"- **Longitudinal Evaluation:** {ci['change_over_time']}")
        lines.append(f"- **Further Assessment Warranted:** {'Yes' if ci['requires_further_assessment'] else 'No (continue routine monitoring)'}")

    # Section 4: Longitudinal Progress & Reliability
    lines.append("\n## 4. Longitudinal Progress and Data Quality")
    unreliable_count = (longitudinal or {}).get("unavailable_or_unreliable_count", 0)
    total_sessions = (longitudinal or {}).get("total_sessions", 1)
    lines.append(f"- Total recorded sessions: **{total_sessions}** (Valid: **{(longitudinal or {}).get('valid_sessions_count', 0)}**, Unavailable/Unreliable: **{unreliable_count}**)")
    excluded_notes = []
    for pt in (longitudinal or {}).get("timeline", []):
        for mk in ("walking_speed", "cadence"):
            m = pt.get(mk, {})
            if m.get("status") not in ("valid", None) and m.get("reason"):
                excluded_notes.append(f"Session {pt.get('date', '')[:10]} ({mk}): {m['reason']}")
    if excluded_notes:
        lines.append("- **Excluded / Unreliable Measurements:**")
        for en in excluded_notes[:10]:
            lines.append(f"  - {en}")

    # Section 5: Clinical Considerations
    considerations: List[str] = []
    if ws.get("trend") == "improved":
        considerations.append("Walking speed has increased since baseline, meeting the >= 0.05 m/s meaningful change threshold.")
    elif ws.get("trend") == "declined":
        considerations.append("Walking speed has decreased since baseline; clinical review of potential fatigue, pain, or protocol differences is warranted.")
    elif ws.get("trend") == "unchanged" and ws.get("valid_count", 0) >= 2:
        considerations.append("Walking speed has remained relatively stable across valid sessions.")
    if cad.get("trend") == "unchanged" and cad.get("valid_count", 0) >= 2:
        considerations.append("Cadence has remained relatively stable.")
    elif cad.get("trend") == "declined":
        considerations.append("Cadence shifted outside the typical 90–130 steps/min walking band; verify compensatory stepping strategies.")
    if unreliable_count > 0:
        considerations.append("Some sessions have unavailable or low-confidence measurements; additional standardized assessments may be appropriate before concluding functional change.")
    if not considerations:
        considerations.append("Insufficient multi-session data to establish longitudinal clinical considerations; repeat standardized capture is recommended.")

    lines.append("\n## 5. Clinical Considerations")
    for c in considerations:
        lines.append(f"- {c}")

    # Section 6: Clinician Notes and Recommendations
    lines.append("\n## 6. Clinician Notes and Recommendations")
    lines.append(f"- **Clinician Notes:** {clinician_notes or 'No clinician notes entered yet.'}")
    if rehabilitation_priorities:
        lines.append("- **Rehabilitation Priorities:**")
        for p in rehabilitation_priorities:
            lines.append(f"  - {p}")
    else:
        lines.append("- **Rehabilitation Priorities:** Pending clinician entry.")
    lines.append(f"- **Follow-up Recommendations:** {recommendations or 'Pending clinician entry.'}")

    lines.append("\n## 7. Limitations and Methodological Notes")
    for lim in assessment.global_limitations:
        lines.append(f"- {lim}")

    structured_data = {
        "patient_info": {
            "subject_id": ctx.subject_id,
            "session_id": ctx.session_id,
            "assessment_date": assessment.created_at.isoformat() if assessment.created_at else None,
            "clinician": clinician_name,
            "comparison_period": period_str,
            "camera_view": ctx.camera_view,
            "calibration_status": ctx.calibration_status,
        },
        "measurement_summary": {
            "walking_speed": ws,
            "cadence": cad,
            "overall_status": assessment.overall_status.value,
            "session_features": [f.model_dump(mode="json") for f in assessment.feature_interpretations],
        },
        "clinical_interpretation": {
            "walking_speed": ws_interp,
            "cadence": cad_interp,
        },
        "longitudinal_progress": {
            "total_sessions": total_sessions,
            "valid_sessions_count": (longitudinal or {}).get("valid_sessions_count", 0),
            "unavailable_or_unreliable_count": unreliable_count,
            "walking_speed_series": ws.get("series", []),
            "cadence_series": cad.get("series", []),
            "excluded_notes": excluded_notes,
        },
        "clinical_considerations": considerations,
        "clinician_section": {
            "clinician_notes": clinician_notes or "",
            "rehabilitation_priorities": rehabilitation_priorities or [],
            "recommendations": recommendations or "",
        },
    }

    return GaitReport(
        report_type=ReportType.professional,
        subject_id=ctx.subject_id,
        session_id=ctx.session_id,
        assessment_id=assessment.assessment_id,
        content_md="\n".join(lines),
        report_data=structured_data,
        limitations=assessment.global_limitations,
        provenance={
            "pose_model": f"{ctx.pose_model} v{ctx.pose_model_version}",
            "rule_version": ctx.assessment_rule_version,
        },
    )
