from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.api.dependencies import get_db, get_config, get_job_manager
from src.api.auth.dependencies import get_current_user, verify_subject_access
from src.api.schemas.api_responses import JobResponse
from src.api.schemas.requests import AnalysisRequest
from src.database.models import User
from src.database.repositories import JobRepository, RecordingRepository, SessionRepository, SubjectRepository
from src.jobs.job_manager import JobManager
from src.jobs.task_registry import run_analysis_pipeline
from src.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["analysis"])


@router.post("/api/v1/sessions/{session_id}/analysis", response_model=JobResponse, status_code=202)
def submit_analysis(
    session_id: str,
    payload: AnalysisRequest,
    db: Session = Depends(get_db),
    jm: JobManager = Depends(get_job_manager),
    config=Depends(get_config),
    current_user: User = Depends(get_current_user),
):
    sess = SessionRepository(db).get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    subj = SubjectRepository(db).get(sess.subject_id)
    if subj:
        verify_subject_access(subj, current_user)

    recording_path = ""
    recording_view = None
    if payload.recording_id:
        rec = RecordingRepository(db).get(payload.recording_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Recording not found")
        if rec.session_id != session_id:
            raise HTTPException(status_code=400, detail="Recording does not belong to this session")
        recording_path = rec.file_path
        recording_view = rec.camera_view

    camera_view = payload.camera_view or recording_view or "side"

    job = JobRepository(db).create(
        session_id=session_id,
        subject_id=sess.subject_id,
        recording_id=payload.recording_id,
        pose_model=payload.pose_model,
    )

    jm.submit(
        job_id=job.id,
        task_fn=run_analysis_pipeline,
        recording_path=recording_path,
        session_id=session_id,
        subject_id=sess.subject_id,
        camera_view=camera_view,
        labelled_view=payload.camera_view or recording_view,
        pose_model=payload.pose_model,
        recording_id=payload.recording_id,
    )
    return job
