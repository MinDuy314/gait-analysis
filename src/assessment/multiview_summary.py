"""Consolidated multi-view assessment summary (Feature 01).

Builds one session-level view of the front / side / rear recordings of an
assessment session: per-view recording status, processing status and
measurements, plus a conservative "combined" table.

Combination policy (documented, intentionally conservative):

* Measurements from different camera views are NEVER averaged.
* Each metric has a set of camera views from which it can be validly measured
  with 2D pose estimation (e.g. sagittal knee ROM only from the side view,
  frontal-plane trunk displacement only from front/rear views, temporal
  parameters such as cadence from any view).
* For each metric, the value is taken from a single source view: the most
  suitable eligible view (by the preference order below), provided the
  measurement is available, its assessment status is ``supported`` or
  ``limited_evidence``, its confidence is at least ``MIN_COMBINE_CONFIDENCE``
  and the pipeline-detected view does not contradict the labelled view.
* When two or more eligible views report the same view-independent metric and
  disagree by more than ``AGREEMENT_TOLERANCE`` (relative), no combined value
  is reported and the metric is flagged as ``conflicting`` for clinician review.
* Metrics without a documented view mapping are not combined; they are shown
  per view only.

Recordings are captured sequentially, not synchronously, and no camera
calibration is performed, so this is NOT a 3D reconstruction.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

CAMERA_VIEWS: Sequence[str] = ("front", "side", "rear")

MIN_COMBINE_CONFIDENCE = 0.5
AGREEMENT_TOLERANCE = 0.10  # 10 % relative difference between views
ELIGIBLE_STATUSES = ("supported", "limited_evidence")

# Metric -> eligible views in order of preference. Matching is by exact name
# first, then by substring rules below.
_EXACT_VIEW_RULES: Dict[str, Sequence[str]] = {
    "cadence": ("side", "front", "rear"),
    "cadence_steps_per_min": ("side", "front", "rear"),
    "stride_time_mean": ("side", "front", "rear"),
    "stride_time_sd": ("side", "front", "rear"),
    "gait_cycle_duration": ("side", "front", "rear"),
    "trunk_lateral_displacement_px": ("front", "rear"),
}
_SUBSTRING_VIEW_RULES: Sequence[tuple] = (
    # Sagittal-plane kinematics and spatial parameters: side view only.
    ("knee_flexion", ("side",)),
    ("hip_flexion", ("side",)),
    ("ankle_angle", ("side",)),
    ("stride_length", ("side",)),
    ("step_length", ("side",)),
    # Frontal-plane parameters: front or rear view.
    ("trunk_lateral", ("front", "rear")),
    ("step_width", ("front", "rear")),
    ("pelvic_obliquity", ("front", "rear")),
)
# View-independent temporal metrics for which cross-view agreement is checked.
_TEMPORAL_PREFIXES = ("cadence", "stride_time", "gait_cycle_duration", "step_time")

NO_3D_LIMITATION = (
    "Views were recorded sequentially without synchronization or camera calibration. "
    "Results are per-view 2D estimates; no 3D reconstruction is performed."
)
NO_AVERAGING_LIMITATION = (
    "Measurements from different camera views are not averaged. Each combined value comes "
    "from a single, most suitable camera view and is reported with its source."
)


def eligible_views_for_metric(feature_name: str) -> Optional[Sequence[str]]:
    """Return eligible views (in preference order) or None when not combinable."""
    if feature_name in _EXACT_VIEW_RULES:
        return _EXACT_VIEW_RULES[feature_name]
    for needle, views in _SUBSTRING_VIEW_RULES:
        if needle in feature_name:
            return views
    return None


def _is_temporal(feature_name: str) -> bool:
    return feature_name.startswith(_TEMPORAL_PREFIXES)


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt is not None else None


def recording_summary(rec) -> Dict[str, Any]:
    return {
        "id": rec.id,
        "camera_view": rec.camera_view,
        "recording_source": rec.recording_source,
        "original_filename": rec.original_filename,
        "recorded_at": _iso(rec.recorded_at),
        "created_at": _iso(rec.created_at),
        "duration_seconds": rec.duration_seconds,
        "fps": rec.fps,
        "width": rec.width,
        "height": rec.height,
        "file_size_bytes": rec.file_size_bytes,
        "validation_status": rec.validation_status,
        "validation_message": rec.validation_message,
        "quality_status": rec.quality_status,
        "measurement_confidence": rec.measurement_confidence,
        "annotation_status": rec.annotation_status,
        "recording_metadata": rec.recording_metadata,
        "is_superseded": bool(rec.is_superseded),
    }


def job_summary(job) -> Optional[Dict[str, Any]]:
    if job is None:
        return None
    return {
        "id": job.id,
        "status": job.status,
        "current_stage": job.current_stage,
        "progress_pct": job.progress_pct,
        "error_message": job.error_message,
        "created_at": _iso(job.created_at),
        "completed_at": _iso(job.completed_at),
    }


def assessment_summary(record, labelled_view: Optional[str]) -> Optional[Dict[str, Any]]:
    if record is None:
        return None
    data = record.assessment_data or {}
    detected_view = (data.get("context") or {}).get("camera_view")
    view_mismatch = bool(
        labelled_view
        and detected_view
        and detected_view not in ("unknown", labelled_view)
    )
    measurements = []
    for fi in data.get("feature_interpretations") or []:
        measurements.append({
            "feature_name": fi.get("feature_name"),
            "category": fi.get("category"),
            "value": fi.get("value"),
            "unit": fi.get("unit") or "",
            "status": fi.get("status"),
            "confidence": fi.get("confidence"),
        })
    return {
        "assessment_id": record.id,
        "overall_status": record.overall_status,
        "approval_status": record.approval_status or "pending_review",
        "analysed_camera_view": detected_view,
        "view_mismatch": view_mismatch,
        "measurements": measurements,
        "limitations": list(data.get("global_limitations") or [])[:5],
        "created_at": _iso(record.created_at),
    }


def view_status(recording, job, assessment) -> str:
    """Status of a single view: missing / recorded / processing / analysed / failed."""
    if recording is None:
        return "missing"
    if job is not None and job.status in ("queued", "running"):
        return "processing"
    if assessment is not None and (job is None or job.status in ("completed", "partially_completed")):
        return "analysed"
    if job is not None and job.status in ("failed", "cancelled"):
        return "failed"
    return "recorded"


def combine_measurements(views: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Conservatively combine per-view measurements (selection, never averaging)."""
    by_metric: Dict[str, Dict[str, Dict[str, Any]]] = {}
    units: Dict[str, str] = {}
    for v in views:
        ass = v.get("assessment")
        if not ass:
            continue
        for m in ass["measurements"]:
            name = m.get("feature_name")
            if not name:
                continue
            by_metric.setdefault(name, {})[v["camera_view"]] = {
                "camera_view": v["camera_view"],
                "recording_id": v["recording"]["id"] if v.get("recording") else None,
                "value": m.get("value"),
                "status": m.get("status"),
                "confidence": m.get("confidence"),
                "view_mismatch": ass["view_mismatch"],
            }
            if m.get("unit"):
                units[name] = m["unit"]

    combined: List[Dict[str, Any]] = []
    not_combined: List[Dict[str, Any]] = []
    for name in sorted(by_metric):
        per_view = [by_metric[name][cv] for cv in CAMERA_VIEWS if cv in by_metric[name]]
        eligible = eligible_views_for_metric(name)
        if eligible is None:
            not_combined.append({
                "feature_name": name,
                "unit": units.get(name, ""),
                "reason": "No documented camera-view mapping for this metric; shown per view only.",
                "per_view": per_view,
            })
            continue

        candidates = [
            pv for pv in per_view
            if pv["camera_view"] in eligible
            and pv["value"] is not None
            and pv["status"] in ELIGIBLE_STATUSES
            and (pv["confidence"] or 0.0) >= MIN_COMBINE_CONFIDENCE
            and not pv["view_mismatch"]
        ]
        entry: Dict[str, Any] = {
            "feature_name": name,
            "unit": units.get(name, ""),
            "eligible_views": list(eligible),
            "per_view": per_view,
            "method": "single_view_selection",
            "value": None,
            "source_view": None,
            "source_recording_id": None,
            "confidence": None,
        }
        if not candidates:
            entry["status"] = "insufficient_data"
            entry["note"] = (
                "No eligible view provided a valid, sufficiently confident measurement "
                f"(eligible views: {', '.join(eligible)})."
            )
            combined.append(entry)
            continue

        candidates.sort(key=lambda pv: (eligible.index(pv["camera_view"]), -(pv["confidence"] or 0.0)))
        chosen = candidates[0]

        if len(candidates) > 1 and _is_temporal(name):
            values = [float(c["value"]) for c in candidates]
            ref = max(abs(x) for x in values) or 1.0
            spread = (max(values) - min(values)) / ref
            if spread > AGREEMENT_TOLERANCE:
                entry["status"] = "conflicting"
                entry["note"] = (
                    f"Views disagree by {spread * 100:.0f}% (> {AGREEMENT_TOLERANCE * 100:.0f}% tolerance); "
                    "no combined value is reported. Clinician review required."
                )
                combined.append(entry)
                continue
            entry["agreement"] = "consistent"
        else:
            entry["agreement"] = "single_source"

        entry.update({
            "status": "combined",
            "value": chosen["value"],
            "source_view": chosen["camera_view"],
            "source_recording_id": chosen["recording_id"],
            "confidence": chosen["confidence"],
            "note": f"Value taken from the {chosen['camera_view']} view (not averaged).",
        })
        combined.append(entry)

    return {"measurements": combined, "not_combined": not_combined}


def build_multiview_summary(
    session,
    subject,
    recordings: Iterable[Any],
    latest_job_for_recording,
    assessment_for_recording,
) -> Dict[str, Any]:
    """Build the consolidated assessment payload for one session.

    ``latest_job_for_recording`` and ``assessment_for_recording`` are callables
    taking a recording id and returning the ORM object (or None).
    """
    recordings = list(recordings)
    active = [r for r in recordings if not r.is_superseded]
    selected = list(session.selected_views or [])

    # Views to display: selected views plus any view that already has a recording.
    recorded_views = {r.camera_view for r in active if r.camera_view in CAMERA_VIEWS}
    display_views = [cv for cv in CAMERA_VIEWS if cv in selected or cv in recorded_views]

    views: List[Dict[str, Any]] = []
    for cv in display_views:
        current = sorted(
            [r for r in active if r.camera_view == cv],
            key=lambda r: r.created_at or datetime.min,
        )
        rec = current[-1] if current else None
        job = latest_job_for_recording(rec.id) if rec else None
        ass_record = assessment_for_recording(rec.id) if rec else None
        ass = assessment_summary(ass_record, cv)
        views.append({
            "camera_view": cv,
            "selected": cv in selected,
            "status": view_status(rec, job, ass_record),
            "recording": recording_summary(rec) if rec else None,
            "retake_count": len([r for r in recordings if r.camera_view == cv and r.is_superseded]),
            "job": job_summary(job),
            "assessment": ass,
        })

    unlabelled = [recording_summary(r) for r in active if r.camera_view not in CAMERA_VIEWS]
    missing_views = [v["camera_view"] for v in views if v["selected"] and v["status"] == "missing"]
    recorded_selected = [v for v in views if v["selected"] and v["status"] != "missing"]

    if not selected:
        recording_status = "not_applicable"
    elif not recorded_selected:
        recording_status = "not_started"
    elif missing_views:
        recording_status = "incomplete"
    else:
        recording_status = "complete"

    analysed = [v for v in views if v["status"] == "analysed"]
    processing = [v for v in views if v["status"] == "processing"]
    failed = [v for v in views if v["status"] == "failed"]

    combination = combine_measurements(analysed)
    limitations = [NO_3D_LIMITATION, NO_AVERAGING_LIMITATION]
    if missing_views:
        limitations.append(
            "Missing views: " + ", ".join(missing_views)
            + ". Metrics that require these views are reported as unavailable, not as normal."
        )
    if any(v["assessment"] and v["assessment"]["view_mismatch"] for v in analysed):
        limitations.append(
            "The automatically detected camera view differs from the labelled view for at least one "
            "recording; its measurements are excluded from combination."
        )

    if not analysed:
        combined_status = "processing" if processing else "not_available"
    elif processing or missing_views or failed or len(analysed) < len([v for v in views if v["recording"]]):
        combined_status = "partial"
    else:
        combined_status = "complete"

    return {
        "session_id": session.id,
        "subject_id": session.subject_id,
        "subject_display_name": getattr(subject, "display_name", None),
        "session_created_at": _iso(session.created_at),
        "session_status": session.session_status,
        "assessment_mode": session.assessment_mode or ("multi_view" if selected else "single_view"),
        "selected_views": selected,
        "recording_status": recording_status,
        "missing_views": missing_views,
        "views": views,
        "unlabelled_recordings": unlabelled,
        "combined": {
            "status": combined_status,
            "analysed_views": [v["camera_view"] for v in analysed],
            "measurements": combination["measurements"],
            "not_combined": combination["not_combined"],
            "method": "single_view_selection",
            "is_3d_reconstruction": False,
            "limitations": limitations,
            "policy": {
                "min_confidence": MIN_COMBINE_CONFIDENCE,
                "agreement_tolerance": AGREEMENT_TOLERANCE,
                "eligible_statuses": list(ELIGIBLE_STATUSES),
            },
        },
    }
