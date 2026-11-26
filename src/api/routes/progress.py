from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.api.auth.dependencies import get_current_user, verify_subject_access
from src.api.schemas.requests import CompareSessionsRequest
from src.database.models import BaselineRecord, ProgressRecord, AssessmentRecord, User
from src.database.repositories import SubjectRepository, SessionRepository
from src.progress.progress_engine import ProgressEngine

router = APIRouter(tags=["progress"])


@router.get("/api/v1/subjects/{subject_id}/progress")
def get_progress(
    subject_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    s = SubjectRepository(db).get(subject_id)
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(s, current_user)
    records = db.query(ProgressRecord).filter(
        ProgressRecord.subject_id == subject_id
    ).order_by(ProgressRecord.created_at.desc()).all()
    return {
        "subject_id": subject_id,
        "progress_records": [
            {
                "id": r.id,
                "comparison_type": r.comparison_type,
                "overall_category": r.overall_category,
                "created_at": r.created_at,
            }
            for r in records
        ],
    }


@router.get("/api/v1/subjects/{subject_id}/baselines")
def get_baselines(
    subject_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    s = SubjectRepository(db).get(subject_id)
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(s, current_user)
    records = db.query(BaselineRecord).filter(
        BaselineRecord.subject_id == subject_id
    ).order_by(BaselineRecord.version.desc()).all()
    return {
        "subject_id": subject_id,
        "baselines": [
            {
                "id": r.id,
                "version": r.version,
                "is_current": r.is_current,
                "n_sessions": r.n_sessions,
                "created_at": r.created_at,
            }
            for r in records
        ],
    }


@router.post("/api/v1/subjects/{subject_id}/compare-sessions")
def compare_sessions(
    subject_id: str,
    payload: CompareSessionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    s = SubjectRepository(db).get(subject_id)
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(s, current_user)
    s1 = SessionRepository(db).get(payload.session_id_1)
    s2 = SessionRepository(db).get(payload.session_id_2)
    if not s1 or not s2:
        raise HTTPException(status_code=404, detail="One or both sessions not found")

    a1 = db.query(AssessmentRecord).filter(
        AssessmentRecord.session_id == payload.session_id_1
    ).order_by(AssessmentRecord.created_at.desc()).first()
    a2 = db.query(AssessmentRecord).filter(
        AssessmentRecord.session_id == payload.session_id_2
    ).order_by(AssessmentRecord.created_at.desc()).first()

    comparability_limitations = []
    if s1.camera_view != s2.camera_view:
        comparability_limitations.append(
            f"Camera view mismatch ({s1.camera_view or 'unknown'} vs {s2.camera_view or 'unknown'}) — direct comparison is limited."
        )
    if not a1 or not a2:
        comparability_limitations.append("One or both sessions lack a completed assessment.")

    comparability = "comparable"
    if not a1 or not a2:
        comparability = "insufficient_data"
    elif s1.camera_view != s2.camera_view:
        comparability = "conditionally_comparable"

    measurement_changes = []
    if a1 and a2 and a1.assessment_data and a2.assessment_data:
        interps1 = {
            f["feature_name"]: f
            for f in (a1.assessment_data.get("feature_interpretations") or [])
            if f.get("value") is not None
        }
        interps2 = {
            f["feature_name"]: f
            for f in (a2.assessment_data.get("feature_interpretations") or [])
            if f.get("value") is not None
        }
        for fname, f1 in interps1.items():
            if fname in interps2:
                f2 = interps2[fname]
                v1 = float(f1["value"])
                v2 = float(f2["value"])
                delta = round(v2 - v1, 3)
                pct = round(((v2 - v1) / v1) * 100.0, 2) if v1 != 0 else None
                measurement_changes.append({
                    "feature_name": fname,
                    "category": f2.get("category") or f1.get("category"),
                    "unit": f2.get("unit") or f1.get("unit") or "",
                    "session_1_value": v1,
                    "session_2_value": v2,
                    "delta": delta,
                    "percent_change": pct,
                })

    return {
        "subject_id": subject_id,
        "session_1": payload.session_id_1,
        "session_2": payload.session_id_2,
        "comparability": comparability,
        "comparability_limitations": comparability_limitations,
        "measurement_changes": measurement_changes,
    }
