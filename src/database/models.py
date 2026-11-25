import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON
)
from sqlalchemy.orm import relationship
from src.database.database import Base


def _uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="individual")  # individual, professional, administrator
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Subject(Base):
    __tablename__ = "subjects"
    id = Column(String, primary_key=True, default=_uuid)
    display_name = Column(String, nullable=True)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sessions = relationship("Session", back_populates="subject")


class Session(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True, default=_uuid)
    subject_id = Column(String, ForeignKey("subjects.id"), nullable=False, index=True)
    walking_speed_ms = Column(Float, nullable=True)
    walking_surface = Column(String, nullable=True)
    slope_deg = Column(Float, nullable=True)
    walking_direction = Column(String, nullable=True)
    footwear = Column(String, nullable=True)
    camera_view = Column(String, nullable=True)
    calibration_status = Column(String, nullable=True)
    height_m = Column(Float, nullable=True)
    mass_kg = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    subject = relationship("Subject", back_populates="sessions")
    recordings = relationship("Recording", back_populates="session")
    jobs = relationship("AnalysisJob", back_populates="session")


class Recording(Base):
    __tablename__ = "recordings"
    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    original_filename = Column(String, nullable=True)
    server_filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    mime_type = Column(String, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    fps = Column(Float, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    validation_status = Column(String, default="pending")
    validation_message = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    session = relationship("Session", back_populates="recordings")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    recording_id = Column(String, ForeignKey("recordings.id"), nullable=True)
    subject_id = Column(String, nullable=False)
    status = Column(String, default="queued")  # queued, running, completed, partially_completed, failed, cancelled
    current_stage = Column(String, nullable=True)
    progress_pct = Column(Float, default=0.0)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    pose_model = Column(String, nullable=True)
    pose_model_version = Column(String, nullable=True)
    config_version = Column(String, nullable=True)
    processing_device = Column(String, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    result_data = Column(JSON, nullable=True)
    session = relationship("Session", back_populates="jobs")


class AssessmentRecord(Base):
    __tablename__ = "assessments"
    id = Column(String, primary_key=True, default=_uuid)
    subject_id = Column(String, nullable=False, index=True)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False, index=True)
    job_id = Column(String, ForeignKey("analysis_jobs.id"), nullable=True)
    assessment_data = Column(JSON, nullable=False)
    overall_status = Column(String, nullable=True)
    pose_model = Column(String, nullable=True)
    rule_version = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BaselineRecord(Base):
    __tablename__ = "baselines"
    id = Column(String, primary_key=True, default=_uuid)
    subject_id = Column(String, nullable=False, index=True)
    version = Column(Integer, default=1)
    is_current = Column(Boolean, default=True)
    baseline_data = Column(JSON, nullable=False)
    n_sessions = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class ProgressRecord(Base):
    __tablename__ = "progress_records"
    id = Column(String, primary_key=True, default=_uuid)
    subject_id = Column(String, nullable=False, index=True)
    current_session_id = Column(String, nullable=False)
    comparison_type = Column(String, nullable=False)
    comparison_session_id = Column(String, nullable=True)
    baseline_id = Column(String, nullable=True)
    progress_data = Column(JSON, nullable=False)
    overall_category = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ReportRecord(Base):
    __tablename__ = "reports"
    id = Column(String, primary_key=True, default=_uuid)
    subject_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True)
    report_type = Column(String, nullable=False)
    assessment_id = Column(String, nullable=True)
    file_path = Column(String, nullable=True)
    status = Column(String, default="generated")
    generated_at = Column(DateTime, default=datetime.utcnow)
    is_deleted = Column(Boolean, default=False)
    provenance = Column(JSON, nullable=True)


class DeletionLog(Base):
    __tablename__ = "deletion_logs"
    id = Column(String, primary_key=True, default=_uuid)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    deleted_by = Column(String, nullable=True)
    reason = Column(String, nullable=True)
    deleted_at = Column(DateTime, default=datetime.utcnow)
