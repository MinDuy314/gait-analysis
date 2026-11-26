from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.api.auth.dependencies import get_current_user, verify_subject_access
from src.api.schemas.api_responses import ReportResponse
from src.api.schemas.requests import ReportRequest
from src.assessment.assessment_engine import AssessmentEngine
from src.assessment.assessment_schema import AssessmentContext
from src.database.models import AssessmentRecord, ReportRecord, User
from src.database.repositories import SessionRepository, SubjectRepository
from src.reporting.individual_report import generate_individual_report
from src.reporting.professional_report import generate_professional_report
from src.reporting.report_renderer import ReportRenderer
import uuid
from datetime import datetime

router = APIRouter(tags=["reports"])


@router.post("/api/v1/sessions/{session_id}/reports", response_model=ReportResponse, status_code=201)
def generate_report(
    session_id: str,
    payload: ReportRequest,
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
    if payload.report_type == "professional" and current_user.role == "individual":
        raise HTTPException(status_code=403, detail="Patients cannot generate clinician reports")

    assessment_record = db.query(AssessmentRecord).filter(
        AssessmentRecord.session_id == session_id
    ).order_by(AssessmentRecord.created_at.desc()).first()

    if assessment_record and assessment_record.assessment_data:
        from src.assessment.assessment_schema import GaitAssessment
        assessment = GaitAssessment.model_validate(assessment_record.assessment_data)
    else:
        ctx = AssessmentContext(
            subject_id=sess.subject_id,
            session_id=session_id,
            camera_view=sess.camera_view,
            walking_speed_ms=sess.walking_speed_ms,
        )
        engine = AssessmentEngine()
        assessment = engine.assess(context=ctx, features={})

    renderer = ReportRenderer()
    if payload.report_type == "individual":
        report = generate_individual_report(assessment)
    elif payload.report_type == "professional":
        report = generate_professional_report(assessment)
    else:
        raise HTTPException(status_code=400, detail="report_type must be 'individual' or 'professional'")

    file_path = renderer.save(report)

    record = ReportRecord(
        id=report.report_id,
        subject_id=sess.subject_id,
        session_id=session_id,
        report_type=payload.report_type,
        assessment_id=assessment.assessment_id,
        file_path=str(file_path),
        status="generated",
        generated_at=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/api/v1/reports/{report_id}", response_model=ReportResponse)
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = db.query(ReportRecord).filter(ReportRecord.id == report_id, ReportRecord.is_deleted == False).first()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    subj = SubjectRepository(db).get(r.subject_id)
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(subj, current_user)
    if r.report_type == "professional" and current_user.role == "individual":
        raise HTTPException(status_code=403, detail="Patients cannot access clinician reports")
    return r


@router.get("/api/v1/reports/{report_id}/download")
def download_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = db.query(ReportRecord).filter(ReportRecord.id == report_id, ReportRecord.is_deleted == False).first()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    subj = SubjectRepository(db).get(r.subject_id)
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(subj, current_user)
    if r.report_type == "professional" and current_user.role == "individual":
        raise HTTPException(status_code=403, detail="Patients cannot download clinician reports")
    if not r.file_path or not Path(r.file_path).exists():
        raise HTTPException(status_code=404, detail="Report file not found on disk")
    return FileResponse(path=r.file_path, media_type="text/markdown", filename=f"report_{report_id}.md")
