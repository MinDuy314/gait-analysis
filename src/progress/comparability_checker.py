from typing import Any, Dict, Optional
from src.progress.progress_schema import ComparabilityDecision


def check_comparability(
    current_ctx: Dict[str, Any],
    reference_ctx: Dict[str, Any],
) -> tuple:
    issues = []

    # Camera view
    curr_view = current_ctx.get("camera_view")
    ref_view = reference_ctx.get("camera_view")
    if curr_view and ref_view and curr_view != ref_view:
        issues.append(
            f"Camera view changed: {ref_view} \u2192 {curr_view}. "
            "View-dependent features may not be comparable."
        )

    # Pose model version
    curr_model = current_ctx.get("pose_model_version")
    ref_model = reference_ctx.get("pose_model_version")
    if curr_model and ref_model and curr_model != ref_model:
        issues.append(
            f"Pose model version changed: {ref_model} \u2192 {curr_model}. "
            "Systematic differences may exist."
        )

    # Walking speed
    curr_speed = current_ctx.get("walking_speed_ms")
    ref_speed = reference_ctx.get("walking_speed_ms")
    if curr_speed is not None and ref_speed is not None:
        speed_diff_pct = abs(curr_speed - ref_speed) / max(ref_speed, 0.1) * 100
        if speed_diff_pct > 20:
            issues.append(
                f"Walking speed difference > 20% ({ref_speed:.2f} vs {curr_speed:.2f} m/s). "
                "Speed-dependent features may not be comparable."
            )

    # Surface/slope
    curr_surf = current_ctx.get("walking_surface")
    ref_surf = reference_ctx.get("walking_surface")
    if curr_surf and ref_surf and curr_surf != ref_surf:
        issues.append(f"Walking surface changed: {ref_surf} \u2192 {curr_surf}.")

    if not issues:
        return ComparabilityDecision.comparable, "Conditions appear compatible."
    elif len(issues) == 1:
        return ComparabilityDecision.conditionally_comparable, " ".join(issues)
    else:
        return ComparabilityDecision.not_comparable, " ".join(issues)
