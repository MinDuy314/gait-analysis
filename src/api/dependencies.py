from typing import Generator
from sqlalchemy.orm import Session
from src.database.database import get_session_factory
from src.storage.file_storage import FileStorage
from src.jobs.job_manager import JobManager
from src.core.config import AppConfig

_config = AppConfig()
_storage = FileStorage(storage_root=_config.project_root / "data" / "uploads")
_job_manager = None


def get_db() -> Generator[Session, None, None]:
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def get_storage() -> FileStorage:
    return _storage


def get_config() -> AppConfig:
    return _config


def get_job_manager() -> JobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager(db_session_factory=get_session_factory())
    return _job_manager
