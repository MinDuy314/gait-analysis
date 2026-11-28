"""Gait-cycle analysis endpoints (Feature 02)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.auth.dependencies import get_current_user, verify_subject_access
from src.api.dependencies import get_db
from src.database.models import GaitCycleAnalysisRecord, User
from src.database.repositories import RecordingRepository, SessionRepository, SubjectRepository

router = APIRouter(tags=["gait-cycles"])


def _serialize(rec: GaitCycleAnalysisRecord, recording=None, include_detail: bool = True) -> dict:
    data = dict(rec.analysis_data or {})
    out = {
        "id": rec.id,
        "session_id": rec.session_id,
        "recording_id": rec.recording_id,
        "job_id": rec.job_id,
        "camera_view": rec.camera_view,
        "recording_camera_view": getattr(recording, "camera_view", None),
        "recording_is_superseded": bool(getattr(recording, "is_superseded", False)),
        "status": rec.status,
        "method_version": rec.method_version,
        "created_at": rec.created_at,
        "updated_at": rec.updated_at,
    }
    if include_detail:
        out["analysis"] = data
    else:
        out["summary"] = {
            "counts": data.get("counts", {}),
            "cadence": data.get("cadence"),
            "phase_metrics": data.get("phase_metrics", []),
            "warnings": data.get("warnings", []),
        }
    return out


def _check_session(session_id: str, db: Session, user: User):
    sess = SessionRepository(db).get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    subj = SubjectRepository(db).get(sess.subject_id)
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(subj, user)
    return sess


@router.get("/api/v1/sessions/{session_id}/gait-cycles")
def list_session_gait_cycles(
    session_id: str,
    include_superseded: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Gait-cycle analyses for every recording in the session (summary per recording)."""
    _check_session(session_id, db, current_user)
    recs = {r.id: r for r in RecordingRepository(db).list_for_session(session_id, include_superseded=True)}
    rows = (
        db.query(GaitCycleAnalysisRecord)
        .filter(GaitCycleAnalysisRecord.session_id == session_id)
        .order_by(GaitCycleAnalysisRecord.created_at.asc())
        .all()
    )
    out = []
    for row in rows:
        recording = recs.get(row.recording_id)
        if recording is not None and recording.is_superseded and not include_superseded:
            continue
        out.append(_serialize(row, recording, include_detail=False))
    return out


@router.get("/api/v1/recordings/{recording_id}/gait-cycles")
def get_recording_gait_cycles(
    recording_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full gait-cycle analysis (events, individual cycles, aggregates, sub-phases) for one recording."""
    recording = RecordingRepository(db).get(recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    _check_session(recording.session_id, db, current_user)
    row: Optional[GaitCycleAnalysisRecord] = (
        db.query(GaitCycleAnalysisRecord)
        .filter(GaitCycleAnalysisRecord.recording_id == recording_id)
        .order_by(GaitCycleAnalysisRecord.updated_at.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="No gait-cycle analysis for this recording")
    return _serialize(row, recording, include_detail=True)
