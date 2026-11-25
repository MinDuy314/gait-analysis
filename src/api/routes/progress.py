from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.api.schemas.requests import CompareSessionsRequest
from src.database.models import BaselineRecord, ProgressRecord, AssessmentRecord
from src.database.repositories import SubjectRepository, SessionRepository
from src.progress.progress_engine import ProgressEngine

router = APIRouter(tags=["progress"])


@router.get("/api/v1/subjects/{subject_id}/progress")
def get_progress(subject_id: str, db: Session = Depends(get_db)):
    s = SubjectRepository(db).get(subject_id)
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found")
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
def get_baselines(subject_id: str, db: Session = Depends(get_db)):
    s = SubjectRepository(db).get(subject_id)
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found")
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
def compare_sessions(subject_id: str, payload: CompareSessionsRequest, db: Session = Depends(get_db)):
    s = SubjectRepository(db).get(subject_id)
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found")
    s1 = SessionRepository(db).get(payload.session_id_1)
    s2 = SessionRepository(db).get(payload.session_id_2)
    if not s1 or not s2:
        raise HTTPException(status_code=404, detail="One or both sessions not found")

    return {
        "subject_id": subject_id,
        "session_1": payload.session_id_1,
        "session_2": payload.session_id_2,
        "comparability": "comparable" if s1.camera_view == s2.camera_view else "conditionally_comparable",
    }
