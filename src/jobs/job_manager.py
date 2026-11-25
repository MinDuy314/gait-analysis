import threading
from typing import Any, Callable, Dict, Optional
from src.core.logging import get_logger

logger = get_logger(__name__)


class JobManager:
    """Lightweight in-process async job manager backed by database for persistence."""

    def __init__(self, db_session_factory: Callable, max_workers: int = 2):
        self._factory = db_session_factory
        self._max_workers = max_workers
        self._semaphore = threading.Semaphore(max_workers)
        self._threads: Dict[str, threading.Thread] = {}

    def submit(self, job_id: str, task_fn: Callable, **kwargs):
        """Submit a job to run in a background worker thread."""
        from src.database.repositories import JobRepository

        def _run():
            with self._semaphore:
                db = self._factory()
                try:
                    repo = JobRepository(db)
                    repo.update_status(job_id, "running", stage="starting", progress=0.0)
                    task_fn(job_id=job_id, db=db, **kwargs)
                except Exception as exc:
                    logger.exception("Job %s failed: %s", job_id, exc)
                    try:
                        repo2 = JobRepository(db)
                        repo2.update_status(job_id, "failed", error=str(exc))
                    except Exception:
                        pass
                finally:
                    db.close()
                    self._threads.pop(job_id, None)

        t = threading.Thread(target=_run, daemon=True, name=f"job-{job_id}")
        self._threads[job_id] = t
        t.start()
        logger.info("Submitted job %s", job_id)

    def cancel(self, job_id: str) -> bool:
        t = self._threads.get(job_id)
        if t and t.is_alive():
            logger.warning("Job %s marked for cancellation", job_id)
        return False

    def wait_all(self, timeout: float = 10.0):
        """Wait for all active background worker threads to finish."""
        threads = list(self._threads.values())
        for t in threads:
            if t.is_alive():
                t.join(timeout=timeout)
