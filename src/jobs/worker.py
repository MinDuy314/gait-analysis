"""Worker for executing asynchronous processing tasks."""
from typing import Any, Callable, Dict
from src.core.logging import get_logger

logger = get_logger(__name__)


class AnalysisWorker:
    """Worker task wrapper for pipeline execution."""

    def __init__(self, task_fn: Callable):
        self.task_fn = task_fn

    def run(self, job_id: str, db, **kwargs) -> Any:
        logger.info("Starting worker for job %s", job_id)
        return self.task_fn(job_id=job_id, db=db, **kwargs)
