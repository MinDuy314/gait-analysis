from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.database.models import AssessmentRecord
from src.database.repositories import SessionRepository

router = APIRouter(tags=["assessments"])


@router.get("/api/v1/sessions/{session_id}/assessment")
def get_assessment(session_id: str, db: Session = Depends(get_db)):
    sess = SessionRepository(db).get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    record = db.query(AssessmentRecord).filter(
        AssessmentRecord.session_id == session_id
    ).order_by(AssessmentRecord.created_at.desc()).first()
    if not record:
        raise HTTPException(status_code=404, detail="No assessment found for this session")
    return {
        "assessment_id": record.id,
        "session_id": session_id,
        "overall_status": record.overall_status,
        "data": record.assessment_data,
        "created_at": record.created_at,
    }
