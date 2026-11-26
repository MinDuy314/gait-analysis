from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.api.auth.dependencies import get_current_user, verify_subject_access
from src.api.schemas.requests import AssessmentUpdateRequest
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
        "recording_id": record.recording_id,
        "overall_status": record.overall_status,
        "approval_status": record.approval_status or "pending_review",
        "clinical_interpretation": record.clinical_interpretation,
        "clinical_notes": None if current_user.role == "individual" else record.clinical_notes,
        "approved_by": record.approved_by,
        "approved_at": record.approved_at,
        "data": data,
        "created_at": record.created_at,
    }


@router.patch("/api/v1/assessments/{assessment_id}")
def update_assessment(
    assessment_id: str,
    payload: AssessmentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("professional", "administrator"):
        raise HTTPException(status_code=403, detail="Only clinicians can update or approve assessments")
    record = db.query(AssessmentRecord).filter(AssessmentRecord.id == assessment_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Assessment not found")
    subj = SubjectRepository(db).get(record.subject_id)
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(subj, current_user)

    if payload.clinical_interpretation is not None:
        record.clinical_interpretation = payload.clinical_interpretation
    if payload.clinical_notes is not None:
        record.clinical_notes = payload.clinical_notes
    if payload.approval_status is not None:
        if payload.approval_status not in ("pending_review", "approved"):
            raise HTTPException(status_code=400, detail="approval_status must be 'pending_review' or 'approved'")
        record.approval_status = payload.approval_status
        if payload.approval_status == "approved":
            record.approved_by = current_user.username
            record.approved_at = datetime.utcnow()
    record.clinician_id = current_user.id
    record.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return {
        "assessment_id": record.id,
        "approval_status": record.approval_status,
        "clinical_interpretation": record.clinical_interpretation,
        "clinical_notes": record.clinical_notes,
        "approved_by": record.approved_by,
        "approved_at": record.approved_at,
    }
