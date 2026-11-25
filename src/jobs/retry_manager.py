"""Retry manager for failed or interrupted jobs."""
from src.database.repositories import JobRepository


class RetryManager:
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries

    def can_retry(self, job) -> bool:
        return job.status in ("failed", "partially_completed") and job.retry_count < self.max_retries

    def prepare_retry(self, repo: JobRepository, job_id: str) -> bool:
        job = repo.get(job_id)
        if not job or not self.can_retry(job):
            return False
        repo.update_status(
            job_id=job_id,
            status="queued",
            stage="pending_retry",
            progress=0.0,
            error=None
        )
        job.retry_count += 1
        repo.db.commit()
        return True
