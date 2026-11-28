from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.api.auth.dependencies import get_current_user, verify_subject_access
from src.api.schemas.api_responses import SessionResponse, PaginatedResponse
from src.api.schemas.requests import SessionCreate, SessionViewsUpdate
from src.assessment.multiview_summary import build_multiview_summary
from src.database.models import AssessmentRecord, GaitCycleAnalysisRecord, User
from src.database.repositories import JobRepository, RecordingRepository, SessionRepository, SubjectRepository

router = APIRouter(tags=["sessions"])


@router.post("/api/v1/subjects/{subject_id}/sessions", response_model=SessionResponse, status_code=201)
def create_session(
    subject_id: str,
    payload: SessionCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subject = SubjectRepository(db).get(subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(subject, current_user)
    repo = SessionRepository(db)

    # Idempotency: a repeated submit (double click, network retry) with the same
    # client_request_id returns the original session instead of creating a duplicate.
    if payload.client_request_id:
        existing = repo.get_by_client_request_id(subject_id, payload.client_request_id)
        if existing:
            response.status_code = 200
            return existing

    data = payload.model_dump(exclude_none=True)
    if data.get("selected_views"):
        data.setdefault("assessment_mode", "multi_view")
        # Keep the legacy single camera_view populated with the primary selected view.
        data.setdefault("camera_view", data["selected_views"][0])
    s = repo.create(subject_id=subject_id, **data)
    return s


@router.get("/api/v1/subjects/{subject_id}/sessions", response_model=PaginatedResponse[SessionResponse])
def list_sessions(
    subject_id: str,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    subject = SubjectRepository(db).get(subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(subject, current_user)
    items = SessionRepository(db).list_for_subject(subject_id, skip, limit)
    return {"items": items, "total": len(items), "skip": skip, "limit": limit}


@router.get("/api/v1/sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    s = SessionRepository(db).get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    subject = SubjectRepository(db).get(s.subject_id)
    if subject:
        verify_subject_access(subject, current_user)
    return s


def _get_accessible_session(session_id: str, db: Session, current_user: User):
    s = SessionRepository(db).get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    subject = SubjectRepository(db).get(s.subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(subject, current_user)
    return s, subject


@router.patch("/api/v1/sessions/{session_id}/views", response_model=SessionResponse)
def update_session_views(
    session_id: str,
    payload: SessionViewsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change which camera views the patient intends to record in this session.

    Existing recordings are never removed; deselecting a view that already has a
    recording keeps the recording (it is still shown in the consolidated assessment).
    """
    s, _ = _get_accessible_session(session_id, db, current_user)
    s.selected_views = payload.selected_views
    s.assessment_mode = "multi_view"
    if not s.camera_view:
        s.camera_view = payload.selected_views[0]
    db.commit()
    db.refresh(s)
    return s


@router.get("/api/v1/sessions/{session_id}/multiview")
def get_multiview_assessment(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Consolidated multi-view assessment: per-view recording/processing/measurement
    status and a conservative combined table (single-view selection, never averaged)."""
    s, subject = _get_accessible_session(session_id, db, current_user)
    recordings = RecordingRepository(db).list_for_session(session_id, include_superseded=True)
    job_repo = JobRepository(db)

    def _latest_job(recording_id: str):
        return job_repo.get_latest_for_session(session_id, recording_id=recording_id)

    def _assessment(recording_id: str):
        return (
            db.query(AssessmentRecord)
            .filter(AssessmentRecord.session_id == session_id, AssessmentRecord.recording_id == recording_id)
            .order_by(AssessmentRecord.created_at.desc())
            .first()
        )

    def _gait_cycle(recording_id: str):
        return (
            db.query(GaitCycleAnalysisRecord)
            .filter(GaitCycleAnalysisRecord.session_id == session_id,
                    GaitCycleAnalysisRecord.recording_id == recording_id)
            .order_by(GaitCycleAnalysisRecord.updated_at.desc())
            .first()
        )

    summary = build_multiview_summary(s, subject, recordings, _latest_job, _assessment, _gait_cycle)
    if current_user.role == "individual":
        # Clinician-only approval details are not exposed to patient accounts.
        for v in summary["views"]:
            if v.get("assessment"):
                v["assessment"].pop("approval_status", None)
    return summary
