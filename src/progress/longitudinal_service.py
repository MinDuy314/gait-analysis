"""Authoritative longitudinal gait progress and measurement reliability service."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session as DBSession

from src.database.models import AnalysisJob, AssessmentRecord, Recording, Session, Subject

# Configurable, evidence-aligned rehabilitation thresholds (never arbitrary clinical diagnoses)
WALKING_SPEED_MEANINGFUL_CHANGE_MS = 0.05   # >= 0.05 m/s meaningful change
CADENCE_MEANINGFUL_CHANGE_SPM = 5.0         # >= 5.0 steps/min meaningful change
CADENCE_TARGET_LOW_SPM = 90.0               # Typical adult walking cadence lower bound
CADENCE_TARGET_HIGH_SPM = 130.0             # Typical adult walking cadence upper bound
MIN_VALID_CONFIDENCE = 0.60


def _classify_feature_reliability(
    value: Optional[float],
    status_str: Optional[str],
    confidence: Optional[float],
    job_status: Optional[str],
    validation_status: Optional[str],
    metric_label: str,
) -> Tuple[Optional[float], str, Optional[str]]:
    """Return (clean_value, reliability_status, exclusion_reason)."""
    if job_status in ("queued", "running"):
        return None, "pending", f"{metric_label} is pending completion of video analysis."
    if job_status == "failed" or validation_status == "failed":
        return None, "invalid", f"{metric_label} excluded because recording validation or analysis failed."

    if value is None:
        return None, "unavailable", f"{metric_label} could not be calculated reliably from the available recording data."

    try:
        num = float(value)
    except (TypeError, ValueError):
        return None, "invalid", f"{metric_label} value is non-numeric."

    if not math.isfinite(num) or num <= 0.0:
        return None, "invalid", f"{metric_label} value ({num}) is invalid or zero."

    if status_str in ("insufficient_data", "not_assessable"):
        return None, "unavailable", f"{metric_label} marked {status_str} due to insufficient usable movement data."

    conf = float(confidence) if confidence is not None else 0.75
    if status_str == "limited_evidence" or conf < MIN_VALID_CONFIDENCE:
        return round(num, 3), "low_confidence", (
            f"{metric_label} has low confidence ({conf:.2f}) and is excluded from primary progress calculations."
        )

    return round(num, 3), "valid", None


def _extract_feature(
    interps: Dict[str, Dict[str, Any]],
    names: List[str],
) -> Tuple[Optional[float], Optional[str], Optional[float]]:
    for n in names:
        if n in interps:
            f = interps[n]
            return f.get("value"), f.get("status"), f.get("confidence")
    return None, None, None


def _classify_walking_speed_trend(
    baseline: Optional[float],
    latest: Optional[float],
    n_valid: int,
) -> Tuple[str, str]:
    """Classify walking speed change using >= 0.05 m/s threshold."""
    if n_valid < 2 or baseline is None or latest is None:
        return "insufficient_data", "At least two valid measurements are required to evaluate longitudinal walking speed change."
    delta = latest - baseline
    if abs(delta) < WALKING_SPEED_MEANINGFUL_CHANGE_MS:
        return "unchanged", (
            f"Walking speed change ({delta:+.2f} m/s) is within the ±{WALKING_SPEED_MEANINGFUL_CHANGE_MS:.2f} m/s stability threshold."
        )
    if delta >= WALKING_SPEED_MEANINGFUL_CHANGE_MS:
        return "improved", (
            f"Walking speed increased by {delta:+.2f} m/s, exceeding the {WALKING_SPEED_MEANINGFUL_CHANGE_MS:.2f} m/s meaningful change threshold."
        )
    return "declined", (
        f"Walking speed decreased by {delta:+.2f} m/s, exceeding the {WALKING_SPEED_MEANINGFUL_CHANGE_MS:.2f} m/s meaningful change threshold."
    )


def _classify_cadence_trend(
    baseline: Optional[float],
    latest: Optional[float],
    n_valid: int,
) -> Tuple[str, str]:
    """Classify cadence without assuming higher cadence is universally beneficial."""
    if n_valid < 2 or baseline is None or latest is None:
        return "insufficient_data", "At least two valid measurements are required to evaluate longitudinal cadence change."
    delta = latest - baseline
    if abs(delta) < CADENCE_MEANINGFUL_CHANGE_SPM:
        return "unchanged", (
            f"Cadence change ({delta:+.1f} steps/min) is within the ±{CADENCE_MEANINGFUL_CHANGE_SPM:.1f} steps/min stability band."
        )

    base_dist = 0.0 if CADENCE_TARGET_LOW_SPM <= baseline <= CADENCE_TARGET_HIGH_SPM else min(
        abs(baseline - CADENCE_TARGET_LOW_SPM), abs(baseline - CADENCE_TARGET_HIGH_SPM)
    )
    curr_dist = 0.0 if CADENCE_TARGET_LOW_SPM <= latest <= CADENCE_TARGET_HIGH_SPM else min(
        abs(latest - CADENCE_TARGET_LOW_SPM), abs(latest - CADENCE_TARGET_HIGH_SPM)
    )

    direction = "increased" if delta > 0 else "decreased"
    if CADENCE_TARGET_LOW_SPM <= latest <= CADENCE_TARGET_HIGH_SPM and curr_dist < base_dist:
        return "improved", (
            f"Cadence {direction} by {delta:+.1f} steps/min into the typical physiological walking range ({CADENCE_TARGET_LOW_SPM:.0f}–{CADENCE_TARGET_HIGH_SPM:.0f} steps/min)."
        )
    if curr_dist > base_dist + CADENCE_MEANINGFUL_CHANGE_SPM:
        return "declined", (
            f"Cadence {direction} by {delta:+.1f} steps/min, moving outside the typical walking cadence range ({CADENCE_TARGET_LOW_SPM:.0f}–{CADENCE_TARGET_HIGH_SPM:.0f} steps/min); clinical review recommended."
        )
    return "unchanged", (
        f"Cadence {direction} by {delta:+.1f} steps/min within or near the typical range; clinical context determines whether this directional change is beneficial."
    )


def _build_metric_summary(
    metric_key: str,
    label: str,
    unit: str,
    timeline: List[Dict[str, Any]],
    classifier_fn,
) -> Dict[str, Any]:
    valid_points = [
        p for p in timeline
        if p[metric_key]["status"] == "valid" and p[metric_key]["value"] is not None
    ]
    n_valid = len(valid_points)
    baseline_pt = valid_points[0] if n_valid >= 1 else None
    latest_pt = valid_points[-1] if n_valid >= 1 else None
    prev_pt = valid_points[-2] if n_valid >= 2 else None

    baseline_val = baseline_pt[metric_key]["value"] if baseline_pt else None
    latest_val = latest_pt[metric_key]["value"] if latest_pt else None
    prev_val = prev_pt[metric_key]["value"] if prev_pt else None

    abs_change = round(latest_val - baseline_val, 3) if (baseline_val is not None and latest_val is not None and n_valid >= 2) else None
    pct_change = round((abs_change / baseline_val) * 100.0, 2) if (abs_change is not None and baseline_val and baseline_val > 0) else None
    change_vs_prev = round(latest_val - prev_val, 3) if (prev_val is not None and latest_val is not None) else None
    pct_vs_prev = round((change_vs_prev / prev_val) * 100.0, 2) if (change_vs_prev is not None and prev_val and prev_val > 0) else None

    trend_status, trend_explanation = classifier_fn(baseline_val, latest_val, n_valid)

    series = [
        {
            "session_id": p["session_id"],
            "date": p["date"],
            "record_type": p["record_type"],
            "value": p[metric_key]["value"] if p[metric_key]["status"] in ("valid", "low_confidence") else None,
            "status": p[metric_key]["status"],
            "confidence": p[metric_key]["confidence"],
            "reason": p[metric_key]["reason"],
            "is_baseline": baseline_pt is not None and p["session_id"] == baseline_pt["session_id"],
            "is_latest": latest_pt is not None and p["session_id"] == latest_pt["session_id"],
        }
        for p in timeline
    ]

    return {
        "metric": metric_key,
        "label": label,
        "unit": unit,
        "baseline_value": baseline_val,
        "baseline_date": baseline_pt["date"] if baseline_pt else None,
        "latest_value": latest_val,
        "latest_date": latest_pt["date"] if latest_pt else None,
        "previous_value": prev_val,
        "absolute_change": abs_change,
        "percentage_change": pct_change,
        "change_vs_previous": change_vs_prev,
        "percentage_change_vs_previous": pct_vs_prev,
        "trend": trend_status,
        "trend_explanation": trend_explanation,
        "valid_count": n_valid,
        "excluded_count": len(timeline) - n_valid,
        "series": series,
    }


def build_longitudinal_progress(db: DBSession, subject_id: str) -> Dict[str, Any]:
    """Compute complete chronological rehabilitation timeline, reliability stats, and trends."""
    subj = db.query(Subject).filter(Subject.id == subject_id, Subject.is_deleted == False).first()
    sessions = (
        db.query(Session)
        .filter(Session.subject_id == subject_id, Session.is_deleted == False)
        .order_by(Session.created_at.asc())
        .all()
    )

    timeline: List[Dict[str, Any]] = []
    quality_counts = {"valid": 0, "low_confidence": 0, "invalid": 0, "unavailable": 0, "pending": 0}

    for idx, sess in enumerate(sessions):
        recordings = (
            db.query(Recording)
            .filter(Recording.session_id == sess.id, Recording.is_deleted == False)
            .order_by(Recording.created_at.asc())
            .all()
        )
        latest_job = (
            db.query(AnalysisJob)
            .filter(AnalysisJob.session_id == sess.id)
            .order_by(AnalysisJob.created_at.desc())
            .first()
        )
        latest_ass = (
            db.query(AssessmentRecord)
            .filter(AssessmentRecord.session_id == sess.id)
            .order_by(AssessmentRecord.created_at.desc())
            .first()
        )

        job_status = latest_job.status if latest_job else ("completed" if latest_ass else "no_analysis")
        val_status = recordings[-1].validation_status if recordings else None

        interps: Dict[str, Dict[str, Any]] = {}
        if latest_ass and latest_ass.assessment_data:
            for f in latest_ass.assessment_data.get("feature_interpretations") or []:
                fname = f.get("feature_name")
                if fname:
                    interps[fname] = f

        # Walking speed (from assessment feature first, else explicit positive session.walking_speed_ms)
        ws_val, ws_stat, ws_conf = _extract_feature(interps, ["walking_speed", "walking_speed_ms", "gait_speed"])
        if ws_val is None and sess.walking_speed_ms is not None and sess.walking_speed_ms > 0:
            ws_val = sess.walking_speed_ms
            ws_stat = "supported"
            ws_conf = 0.8 if (sess.calibration_status or "").lower() != "uncalibrated" else 0.7

        clean_ws, ws_rel, ws_reason = _classify_feature_reliability(
            ws_val, ws_stat, ws_conf, job_status, val_status, "Walking speed"
        )

        # Cadence (steps/min)
        cad_val, cad_stat, cad_conf = _extract_feature(interps, ["cadence_steps_per_min", "cadence"])
        clean_cad, cad_rel, cad_reason = _classify_feature_reliability(
            cad_val, cad_stat, cad_conf, job_status, val_status, "Cadence"
        )

        # Overall session quality status
        statuses = {ws_rel, cad_rel}
        if "valid" in statuses:
            overall_quality = "valid"
        elif "pending" in statuses:
            overall_quality = "pending"
        elif "low_confidence" in statuses:
            overall_quality = "low_confidence"
        elif "invalid" in statuses:
            overall_quality = "invalid"
        else:
            overall_quality = "unavailable"
        quality_counts[overall_quality] += 1

        record_type = "clinical_assessment" if (latest_ass and latest_ass.approval_status == "approved") else "session"

        timeline.append({
            "index": idx + 1,
            "session_id": sess.id,
            "assessment_id": latest_ass.id if latest_ass else None,
            "approval_status": latest_ass.approval_status if latest_ass else None,
            "record_type": record_type,
            "date": sess.created_at.isoformat() if sess.created_at else None,
            "camera_view": sess.camera_view,
            "calibration_status": sess.calibration_status,
            "analysis_status": job_status,
            "quality_status": overall_quality,
            "recording_count": len(recordings),
            "recording_ids": [r.id for r in recordings],
            "notes": sess.notes,
            "walking_speed": {
                "value": clean_ws,
                "unit": "m/s",
                "status": ws_rel,
                "confidence": ws_conf,
                "reason": ws_reason,
            },
            "cadence": {
                "value": clean_cad,
                "unit": "steps/min",
                "status": cad_rel,
                "confidence": cad_conf,
                "reason": cad_reason,
            },
        })

    ws_summary = _build_metric_summary(
        "walking_speed", "Walking Speed", "m/s", timeline, _classify_walking_speed_trend
    )
    cad_summary = _build_metric_summary(
        "cadence", "Cadence", "steps/min", timeline, _classify_cadence_trend
    )

    return {
        "subject_id": subject_id,
        "subject_name": subj.display_name if subj else None,
        "total_sessions": len(timeline),
        "valid_sessions_count": quality_counts["valid"],
        "unavailable_or_unreliable_count": len(timeline) - quality_counts["valid"],
        "quality_counts": quality_counts,
        "period_start": timeline[0]["date"] if timeline else None,
        "period_end": timeline[-1]["date"] if timeline else None,
        "walking_speed": ws_summary,
        "cadence": cad_summary,
        "timeline": timeline,
    }
