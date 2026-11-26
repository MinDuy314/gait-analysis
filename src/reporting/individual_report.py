"""Patient-friendly gait rehabilitation report generator."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from src.assessment.assessment_schema import GaitAssessment
from src.progress.progress_schema import ProgressReport
from src.reporting.report_schema import GaitReport, ReportType


def generate_individual_report(
    assessment: GaitAssessment,
    progress: Optional[ProgressReport] = None,
    session_summary: Optional[Dict[str, Any]] = None,
    longitudinal: Optional[Dict[str, Any]] = None,
    clinician_notes: Optional[str] = None,
    rehabilitation_priorities: Optional[List[str]] = None,
    recommendations: Optional[str] = None,
) -> GaitReport:
    ctx = assessment.context
    ws = (longitudinal or {}).get("walking_speed") or {}
    cad = (longitudinal or {}).get("cadence") or {}
    period_start = (longitudinal or {}).get("period_start")
    period_end = (longitudinal or {}).get("period_end")
    period_str = f"{period_start[:10]} to {period_end[:10]}" if period_start and period_end else "Current session"

    # 1. Plain-language overall summary ("Am I making progress?")
    ws_trend = ws.get("trend", "insufficient_data")
    cad_trend = cad.get("trend", "insufficient_data")

    if ws_trend == "improved" and cad_trend == "improved":
        overall_summary = "Your walking speed and step rhythm have improved compared with your earlier assessments."
    elif ws_trend == "improved":
        overall_summary = "Your walking speed has improved compared with your first assessment."
    elif cad_trend == "improved":
        overall_summary = "Your step rhythm (cadence) has moved closer to a steady walking pace compared with your earlier assessment."
    elif ws_trend == "unchanged" or cad_trend == "unchanged":
        overall_summary = "Your walking measurements have remained relatively stable across your recent sessions."
    elif ws_trend == "declined" or cad_trend == "declined":
        overall_summary = "Your recent measurements show some variation. Your physiotherapist or clinician will review these results with you."
    else:
        overall_summary = "More recorded walking sessions are needed before your overall progress can be evaluated reliably."

    # 2. Achievements ("What have I improved?")
    achievements: List[str] = []
    if ws_trend == "improved" and ws.get("absolute_change") is not None:
        achievements.append(
            f"Your walking speed increased by {ws['absolute_change']:.2f} m/s (from {ws['baseline_value']:.2f} m/s to {ws['latest_value']:.2f} m/s) during {period_str}."
        )
    if cad_trend == "improved" and cad.get("latest_value") is not None:
        achievements.append(
            f"Your step rhythm is now {cad['latest_value']:.0f} steps per minute, moving into a comfortable walking range."
        )
    if ws_trend == "unchanged" and ws.get("valid_count", 0) >= 2 and ws.get("latest_value") is not None:
        achievements.append(
            f"Your walking speed has stayed consistent around {ws['latest_value']:.2f} m/s across {ws['valid_count']} sessions."
        )
    if cad_trend == "unchanged" and cad.get("valid_count", 0) >= 2 and cad.get("latest_value") is not None:
        achievements.append(
            f"Your step rhythm has stayed steady around {cad['latest_value']:.0f} steps per minute across {cad['valid_count']} sessions."
        )
    if not achievements:
        achievements.append("You completed a walking recording that will serve as a reference point for tracking future progress.")

    # 3. Areas to improve ("What should I continue working on?")
    areas_to_improve: List[str] = []
    if ws.get("latest_value") is None:
        areas_to_improve.append(
            "Your walking speed could not be measured in this video because distance calibration was not available."
        )
    elif ws_trend == "unchanged" and ws.get("valid_count", 0) >= 2:
        areas_to_improve.append(
            "Your walking speed has not changed significantly yet; continuing regular guided practice can help build strength and confidence."
        )
    elif ws_trend == "declined":
        areas_to_improve.append(
            "Your recent walking speed was lower than your earlier measurement; your clinician will check whether fatigue, pace, or comfort played a role."
        )

    if cad.get("latest_value") is None:
        areas_to_improve.append(
            "Your step rhythm could not be measured reliably in the latest recording; recording a clear full-body walk will help."
        )
    elif cad_trend == "declined":
        areas_to_improve.append(
            "Your step rhythm varied from your earlier sessions; focusing on an even, steady pace may be helpful."
        )

    if (longitudinal or {}).get("valid_sessions_count", 0) < 2:
        areas_to_improve.append(
            "More assessments are needed before your long-term progress can be evaluated reliably."
        )

    # 4. Plain-language chart captions
    ws_caption = (
        f"Walking speed shows how fast you walk in meters per second (m/s). Latest measurement: {ws['latest_value']:.2f} m/s."
        if ws.get("latest_value") is not None
        else "Walking speed is not available for the recorded sessions because distance calibration was not set."
    )
    cad_caption = (
        f"Step rhythm (cadence) counts how many steps you take each minute. Latest measurement: {cad['latest_value']:.0f} steps/min."
        if cad.get("latest_value") is not None
        else "Step rhythm could not be measured reliably yet."
    )

    # 5. Clinician-approved next steps (never auto-generated unapproved treatment instructions)
    next_steps = list(rehabilitation_priorities or [])
    if recommendations:
        next_steps.append(recommendations)

    lines = [
        "# Gait Analysis Summary",
        f"\n*Session: {ctx.session_id} | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*",
        "\n---",
        "\n## Am I Making Progress?",
        f"\n{overall_summary}",
        "\n## What You Have Improved (Achievements)",
    ]
    for a in achievements:
        lines.append(f"- {a}")

    lines.append("\n## Areas to Continue Working On")
    for area in areas_to_improve:
        lines.append(f"- {area}")

    lines.append("\n## Your Measurements Explained")
    lines.append(f"- **Walking Speed:** {ws_caption}")
    lines.append(f"- **Step Rhythm (Cadence):** {cad_caption}")

    lines.append("\n## Next Steps Approved by Your Clinician")
    if next_steps:
        for ns in next_steps:
            lines.append(f"- {ns}")
    else:
        lines.append("- Your clinician will add personalized next steps after reviewing this report.")

    lines.append("\n## Important Notes")
    lines.append("- This summary explains your walking measurements in everyday language and supports conversations with your clinician.")
    for lim in assessment.global_limitations:
        lines.append(f"- {lim}")

    structured_data = {
        "overall_summary": overall_summary,
        "comparison_period": period_str,
        "achievements": achievements,
        "areas_to_improve": areas_to_improve,
        "charts": {
            "walking_speed": {
                "unit": "m/s",
                "latest_value": ws.get("latest_value"),
                "baseline_value": ws.get("baseline_value"),
                "trend": ws_trend,
                "explanation": ws_caption,
                "series": ws.get("series", []),
            },
            "cadence": {
                "unit": "steps/min",
                "latest_value": cad.get("latest_value"),
                "baseline_value": cad.get("baseline_value"),
                "trend": cad_trend,
                "explanation": cad_caption,
                "series": cad.get("series", []),
            },
        },
        "clinician_approved_next_steps": next_steps,
        "clinician_notes": clinician_notes or "",
    }

    return GaitReport(
        report_type=ReportType.individual,
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
