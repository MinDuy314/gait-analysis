from typing import Any, Dict, List, Optional
import numpy as np
from src.progress.progress_schema import (
    ComparabilityDecision, FeatureChange, ProgressCategory, ProgressReport,
)
from src.progress.comparability_checker import check_comparability

# Threshold: change must exceed 1 SD of baseline variability to classify as meaningful
SD_THRESHOLD = 1.0
MIN_RELATIVE_CHANGE_PCT = 5.0  # 5% minimum relative change


def classify_change(
    absolute_change: float,
    baseline_sd: Optional[float],
    feature_name: str,
) -> ProgressCategory:
    # Cannot classify if change is negligible
    if abs(absolute_change) < 1e-6:
        return ProgressCategory.no_meaningful_change

    if baseline_sd is not None and baseline_sd > 0:
        change_in_sd = abs(absolute_change) / baseline_sd
        if change_in_sd < SD_THRESHOLD:
            return ProgressCategory.no_meaningful_change
        return ProgressCategory.improvement if absolute_change > 0 else ProgressCategory.deterioration
    else:
        # No baseline SD — insufficient evidence
        return ProgressCategory.insufficient_evidence


def compare_to_baseline(
    subject_id: str,
    current_session_id: str,
    current_features: Dict[str, Any],
    baseline,  # Baseline object
    current_ctx: Optional[Dict[str, Any]] = None,
    baseline_ctx: Optional[Dict[str, Any]] = None,
) -> ProgressReport:
    comp_decision, comp_note = ComparabilityDecision.comparable, ""
    if current_ctx and baseline_ctx:
        comp_decision, comp_note = check_comparability(current_ctx, baseline_ctx)

    feature_changes: List[FeatureChange] = []
    comparability_issues = (
        [comp_note] if comp_note and comp_decision != ComparabilityDecision.comparable else []
    )

    for feat, curr_val in current_features.items():
        base_val = baseline.feature_means.get(feat)
        base_sd = baseline.feature_sds.get(feat)

        if curr_val is None or base_val is None:
            feature_changes.append(FeatureChange(
                feature_name=feat,
                baseline_value=base_val,
                current_value=curr_val if isinstance(curr_val, (int, float)) else None,
                category=ProgressCategory.insufficient_evidence,
                comparability=ComparabilityDecision.insufficient_data,
                comparability_note="Missing current or baseline value.",
            ))
            continue

        if not isinstance(curr_val, (int, float)) or not isinstance(base_val, (int, float)):
            continue

        curr_f = float(curr_val)
        base_f = float(base_val)
        abs_change = curr_f - base_f
        rel_change = (abs_change / abs(base_f) * 100) if abs(base_f) > 1e-6 else None
        change_sd = abs_change / base_sd if base_sd and base_sd > 0 else None

        if comp_decision == ComparabilityDecision.not_comparable:
            cat = ProgressCategory.insufficient_evidence
        else:
            cat = classify_change(abs_change, base_sd, feat)

        feature_changes.append(FeatureChange(
            feature_name=feat,
            baseline_value=base_f,
            current_value=curr_f,
            absolute_change=abs_change,
            relative_change_pct=rel_change,
            baseline_sd=base_sd,
            change_in_sd_units=change_sd,
            category=cat,
            comparability=comp_decision,
            comparability_note=comp_note,
            confidence=0.7 if comp_decision == ComparabilityDecision.comparable else 0.4,
        ))

    # Overall category
    cats = [fc.category for fc in feature_changes]
    if ProgressCategory.improvement in cats:
        overall = ProgressCategory.improvement
    elif ProgressCategory.deterioration in cats:
        overall = ProgressCategory.deterioration
    elif ProgressCategory.no_meaningful_change in cats:
        overall = ProgressCategory.no_meaningful_change
    else:
        overall = ProgressCategory.insufficient_evidence

    return ProgressReport(
        subject_id=subject_id,
        current_session_id=current_session_id,
        comparison_type="baseline",
        baseline_id=baseline.baseline_id,
        feature_changes=feature_changes,
        overall_category=overall,
        comparability_issues=comparability_issues,
    )
