from src.assessment.assessment_schema import GaitAssessment


def generate_plain_explanation(assessment: GaitAssessment) -> str:
    lines = [
        f"Assessment ID: {assessment.assessment_id}",
        f"Status: {assessment.overall_status.value}",
        "",
    ]
    for interp in assessment.feature_interpretations:
        lines.append(f"- {interp.feature_name}: {interp.interpretation_text}")
    if assessment.bilateral_results:
        lines.append("\nBilateral Comparison:")
        for b in assessment.bilateral_results:
            lines.append(f"  {b.feature_name}: {b.interpretation}")
    if assessment.global_limitations:
        lines.append("\nLimitations:")
        for lim in assessment.global_limitations:
            lines.append(f"  * {lim}")
    return "\n".join(lines)
