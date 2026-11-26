import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session as DBSession
from src.database.models import (
    User, Subject, Session, Recording, AnalysisJob,
    AssessmentRecord, BaselineRecord, ProgressRecord, ReportRecord, DeletionLog
)


class SubjectRepository:
    def __init__(self, db: DBSession):
        self.db = db

    def create(self, owner_id: Optional[str] = None, display_name: Optional[str] = None) -> Subject:
        s = Subject(id=str(uuid.uuid4()), owner_id=owner_id, display_name=display_name)
        self.db.add(s)
        self.db.commit()
        self.db.refresh(s)
        return s

    def get(self, subject_id: str) -> Optional[Subject]:
        return self.db.query(Subject).filter(Subject.id == subject_id, Subject.is_deleted == False).first()

    def list_all(self, skip: int = 0, limit: int = 50) -> List[Subject]:
        return self.db.query(Subject).filter(Subject.is_deleted == False).offset(skip).limit(limit).all()

    def soft_delete(self, subject_id: str, deleted_by: Optional[str] = None) -> bool:
        s = self.get(subject_id)
        if not s:
            return False
        s.is_deleted = True
        s.updated_at = datetime.utcnow()
        log = DeletionLog(entity_type="subject", entity_id=subject_id, deleted_by=deleted_by)
        self.db.add(log)
        self.db.commit()
        return True


class SessionRepository:
    def __init__(self, db: DBSession):
        self.db = db

    def create(self, subject_id: str, **kwargs) -> Session:
        s = Session(id=str(uuid.uuid4()), subject_id=subject_id, **kwargs)
        self.db.add(s)
        self.db.commit()
        self.db.refresh(s)
        return s

    def get(self, session_id: str) -> Optional[Session]:
        return self.db.query(Session).filter(Session.id == session_id, Session.is_deleted == False).first()

    def list_for_subject(self, subject_id: str, skip: int = 0, limit: int = 50) -> List[Session]:
        return (
            self.db.query(Session)
            .filter(Session.subject_id == subject_id, Session.is_deleted == False)
            .offset(skip).limit(limit).all()
        )


class RecordingRepository:
    def __init__(self, db: DBSession):
        self.db = db

    def create(self, session_id: str, server_filename: str, file_path: str, **kwargs) -> Recording:
        r = Recording(id=str(uuid.uuid4()), session_id=session_id, server_filename=server_filename, file_path=file_path, **kwargs)
        self.db.add(r)
        self.db.commit()
        self.db.refresh(r)
        return r

    def get(self, recording_id: str) -> Optional[Recording]:
        return self.db.query(Recording).filter(Recording.id == recording_id, Recording.is_deleted == False).first()

    def list_for_session(self, session_id: str) -> List[Recording]:
        return self.db.query(Recording).filter(Recording.session_id == session_id, Recording.is_deleted == False).all()

    def update_validation(
        self,
        recording_id: str,
        status: str,
        message: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        fps: Optional[float] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> bool:
        """Persist video validation status and extracted metadata."""
        r = self.get(recording_id)
        if not r:
            return False
        r.validation_status = status
        if message is not None:
            r.validation_message = message
        if duration_seconds is not None:
            r.duration_seconds = duration_seconds
        if fps is not None:
            r.fps = fps
        if width is not None:
            r.width = width
        if height is not None:
            r.height = height
        self.db.commit()
        return True

    def update_annotation(
        self,
        recording_id: str,
        annotated_video_path: Optional[str],
        annotation_status: str,
    ) -> bool:
        """Persist annotation result. Returns True if the recording was found."""
        r = self.get(recording_id)
        if not r:
            return False
        r.annotated_video_path = annotated_video_path
        r.annotation_status = annotation_status
        self.db.commit()
        return True


class JobRepository:
    def __init__(self, db: DBSession):
        self.db = db

    def create(self, session_id: str, subject_id: str, recording_id: Optional[str] = None, **kwargs) -> AnalysisJob:
        j = AnalysisJob(id=str(uuid.uuid4()), session_id=session_id, subject_id=subject_id, recording_id=recording_id, **kwargs)
        self.db.add(j)
        self.db.commit()
        self.db.refresh(j)
        return j

    def get(self, job_id: str) -> Optional[AnalysisJob]:
        return self.db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()

    def get_latest_for_session(self, session_id: str) -> Optional[AnalysisJob]:
        return (
            self.db.query(AnalysisJob)
            .filter(AnalysisJob.session_id == session_id)
            .order_by(AnalysisJob.created_at.desc())
            .first()
        )

    def update_status(
        self,
        job_id: str,
        status: str,
        stage: Optional[str] = None,
        progress: Optional[float] = None,
        error: Optional[str] = None,
        result: Optional[Dict] = None,
        processed_frames: Optional[int] = None,
        total_frames: Optional[int] = None,
    ):
        j = self.get(job_id)
        if not j:
            return
        j.status = status
        if stage:
            j.current_stage = stage
        if progress is not None:
            j.progress_pct = progress
        if processed_frames is not None:
            j.processed_frames = processed_frames
        if total_frames is not None:
            j.total_frames = total_frames
        if error:
            j.error_message = error
        if result is not None:
            j.result_data = result
        if status == "running" and not j.started_at:
            j.started_at = datetime.utcnow()
        if status in ("completed", "failed", "cancelled", "partially_completed"):
            j.completed_at = datetime.utcnow()
        self.db.commit()
