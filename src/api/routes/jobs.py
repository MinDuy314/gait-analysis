from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.api.dependencies import get_db, get_job_manager
from src.api.schemas.api_responses import JobResponse
from src.database.repositories import JobRepository
from src.jobs.job_manager import JobManager
from src.jobs.task_registry import run_analysis_pipeline

router = APIRouter(tags=["jobs"])


@router.get("/api/v1/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    j = JobRepository(db).get(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    return j


@router.post("/api/v1/jobs/{job_id}/retry", response_model=JobResponse)
def retry_job(job_id: str, db: Session = Depends(get_db), jm: JobManager = Depends(get_job_manager)):
    j = JobRepository(db).get(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    if j.status not in ("failed", "partially_completed"):
        raise HTTPException(status_code=400, detail=f"Cannot retry job with status {j.status}")

    j.retry_count += 1
    JobRepository(db).update_status(job_id, "queued", stage="queued_retry", progress=0.0)

    jm.submit(
        job_id=job_id,
        task_fn=run_analysis_pipeline,
        recording_path="",
        session_id=j.session_id,
        subject_id=j.subject_id,
        pose_model=j.pose_model or "yolo",
    )
    db.refresh(j)
    return j


@router.post("/api/v1/jobs/{job_id}/cancel", status_code=200)
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    j = JobRepository(db).get(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="Job not found")
    if j.status in ("completed", "failed", "cancelled"):
        return {"detail": f"Job already in terminal state: {j.status}"}
    JobRepository(db).update_status(job_id, "cancelled")
    return {"detail": "Cancellation requested."}
