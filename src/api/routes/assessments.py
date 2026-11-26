from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.api.auth.dependencies import get_current_user, verify_subject_access
from src.database.models import AssessmentRecord, User
from src.database.repositories import SessionRepository, SubjectRepository

router = APIRouter(tags=["assessments"])


@router.get("/api/v1/sessions/{session_id}/assessment")
def get_assessment(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sess = SessionRepository(db).get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    subj = SubjectRepository(db).get(sess.subject_id)
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(subj, current_user)

    record = db.query(AssessmentRecord).filter(
        AssessmentRecord.session_id == session_id
    ).order_by(AssessmentRecord.created_at.desc()).first()
    if not record:
        raise HTTPException(status_code=404, detail="No assessment found for this session")

    data = dict(record.assessment_data or {})
    if current_user.role == "individual":
        # Strip clinician-only technical fields for patient accounts
        data.pop("reference_comparisons", None)

    return {
        "assessment_id": record.id,
        "session_id": session_id,
        "overall_status": record.overall_status,
        "data": data,
        "created_at": record.created_at,
    }
