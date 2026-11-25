from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.api.dependencies import get_db, get_config, get_job_manager
from src.api.schemas.api_responses import JobResponse
from src.api.schemas.requests import AnalysisRequest
from src.database.repositories import JobRepository, RecordingRepository, SessionRepository
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
):
    sess = SessionRepository(db).get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    recording_path = ""
    if payload.recording_id:
        rec = RecordingRepository(db).get(payload.recording_id)
        if not rec:
            raise HTTPException(status_code=404, detail="Recording not found")
        recording_path = rec.file_path

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
        camera_view=payload.camera_view,
        pose_model=payload.pose_model,
        recording_id=payload.recording_id,
    )
    db.refresh(job)
    return job
