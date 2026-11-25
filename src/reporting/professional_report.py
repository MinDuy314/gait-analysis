from datetime import datetime
from typing import Any, Dict, Optional
from src.assessment.assessment_schema import GaitAssessment
from src.progress.progress_schema import ProgressReport
from src.reporting.report_schema import GaitReport, ReportType


def generate_professional_report(
    assessment: GaitAssessment,
    progress: Optional[ProgressReport] = None,
    session_summary: Optional[Dict[str, Any]] = None,
) -> GaitReport:
    lines = [
        "# Professional Gait Analysis Report",
        f"\n*Session: {assessment.context.session_id} | Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*",
        "\n---",
        "\n## 1. Session Context",
    ]

    ctx = assessment.context
    speed_str = f"{ctx.walking_speed_ms:.2f} m/s" if ctx.walking_speed_ms is not None else "not specified"
    slope_str = f"{ctx.slope_deg:.1f} deg" if ctx.slope_deg is not None else "not specified"

    lines.append("| Parameter | Value |")
    lines.append("|-----------|-------|")
    lines.append(f"| Subject ID | {ctx.subject_id} |")
    lines.append(f"| Camera View | {ctx.camera_view or 'not specified'} |")
    lines.append(f"| Calibration | {ctx.calibration_status or 'not specified'} |")
    lines.append(f"| Walking Speed | {speed_str} |")
    lines.append(f"| Surface | {ctx.walking_surface or 'not specified'} |")
    lines.append(f"| Slope | {slope_str} |")
    lines.append(f"| Footwear | {ctx.footwear or 'not specified'} |")
    lines.append(f"| Pose Model | {ctx.pose_model} v{ctx.pose_model_version} |")
    lines.append(f"| Assessment Rules | v{ctx.assessment_rule_version} |")

    lines.append("\n## 2. Biomechanical Measurements")
    lines.append(f"\nOverall Assessment Status: **{assessment.overall_status.value}**\n")

    for interp in assessment.feature_interpretations:
        lines.append(f"### {interp.feature_name}")
        val_str = f"{interp.value:.2f} {interp.unit}" if interp.value is not None else "N/A"
        lines.append(f"- Value: {val_str}")
        lines.append(f"- Status: {interp.status.value}")
        lines.append(f"- Confidence: {interp.confidence:.2f}")
        lines.append(f"- Interpretation: {interp.interpretation_text}")
        if interp.evidence_sources:
            lines.append(f"- Evidence sources: {', '.join(interp.evidence_sources)}")
        if interp.limitations:
            lines.append(f"- Limitations: {'; '.join(interp.limitations)}")

    if assessment.reference_comparisons:
        lines.append("\n## 3. Statistical Reference Comparisons")
        lines.append("*Reference: Research motion-capture dataset. Not validated clinical norms.*\n")
        lines.append("| Feature | Value | Ref Median | Ref SD | Percentile | Z-Score | Comparability |")
        lines.append("|---------|-------|------------|--------|------------|---------|---------------|")
        for rc in assessment.reference_comparisons:
            median_str = f"{rc.reference_median:.2f}" if rc.reference_median is not None else "N/A"
            sd_str = f"{rc.reference_sd:.2f}" if rc.reference_sd is not None else "N/A"
            pct_str = f"{rc.percentile_position:.1f}" if rc.percentile_position is not None else "N/A"
            z_str = f"{rc.z_score:.2f}" if rc.z_score is not None else "N/A"
            val_str = f"{rc.value:.2f}" if rc.value is not None else "N/A"
            lines.append(
                f"| {rc.feature_name} | {val_str} | {median_str} | {sd_str} | "
                f"{pct_str} | {z_str} | {rc.comparability.value} |"
            )

    if assessment.bilateral_results:
        lines.append("\n## 4. Bilateral Comparison")
        lines.append("| Feature | Primary | Contralateral | Abs Diff | Symmetry Index | Side Mapping |")
        lines.append("|---------|---------|---------------|----------|----------------|--------------|")
        for b in assessment.bilateral_results:
            pv = f"{b.primary_value:.2f}" if b.primary_value is not None else "N/A"
            cv = f"{b.contra_value:.2f}" if b.contra_value is not None else "N/A"
            ad = f"{b.absolute_difference:.2f}" if b.absolute_difference is not None else "N/A"
            si = f"{b.symmetry_index:.1f}%" if b.symmetry_index is not None else "N/A"
            sm = "verified" if b.side_mapping_verified else "unverified"
            lines.append(f"| {b.feature_name} | {pv} | {cv} | {ad} | {si} | {sm} |")

    if progress:
        lines.append("\n## 5. Progress Analysis")
        lines.append(f"\nOverall Progress: **{progress.overall_category.value}**\n")
        if progress.comparability_issues:
            lines.append(f"> **Comparability note:** {progress.comparability_issues[0]}\n")
        lines.append("| Feature | Baseline | Current | Change | Change (SD) | Category |")
        lines.append("|---------|----------|---------|--------|-------------|----------|")
        for fc in progress.feature_changes:
            bv = f"{fc.baseline_value:.3f}" if fc.baseline_value is not None else "N/A"
            cv = f"{fc.current_value:.3f}" if fc.current_value is not None else "N/A"
            ch = f"{fc.absolute_change:+.3f}" if fc.absolute_change is not None else "N/A"
            sd_ch = f"{fc.change_in_sd_units:+.2f}" if fc.change_in_sd_units is not None else "N/A"
            lines.append(f"| {fc.feature_name} | {bv} | {cv} | {ch} | {sd_ch} | {fc.category.value} |")

    lines.append("\n## 6. Global Limitations")
    lines.append(
        "\n> [!IMPORTANT]\n> This report is generated from video-based pose estimation. "
        "It is not a clinical assessment and must not be used as a substitute for professional clinical evaluation."
    )
    for lim in assessment.global_limitations:
        lines.append(f"- {lim}")

    lines.append("\n---")
    lines.append(
        "*This report is for research and professional use. It is not a clinical diagnosis. "
        "Statistical reference ranges are from a research motion-capture dataset and are not validated clinical norms.*"
    )

    content = "\n".join(lines)
    return GaitReport(
        report_type=ReportType.professional,
        subject_id=assessment.context.subject_id,
        session_id=assessment.context.session_id,
        assessment_id=assessment.assessment_id,
        content_md=content,
        limitations=assessment.global_limitations,
        provenance={
            "pose_model": ctx.pose_model,
            "pose_model_version": ctx.pose_model_version,
            "assessment_rule_version": ctx.assessment_rule_version,
            "feature_extraction_version": ctx.feature_extraction_version,
        },
    )
