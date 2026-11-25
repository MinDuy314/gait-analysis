"""Tests for Milestone 6: Job manager and pipeline."""
import pytest
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from src.database.database import Base
from src.database import models  # noqa
from src.database.repositories import JobRepository, SubjectRepository, SessionRepository
from src.jobs.job_manager import JobManager
from src.jobs.task_registry import run_analysis_pipeline


@pytest.fixture
def db_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SL = sessionmaker(bind=engine)
    yield SL
    engine.dispose()


def test_job_submission_and_completion(db_factory):
    db = db_factory()
    sub = SubjectRepository(db).create()
    sess = SessionRepository(db).create(subject_id=sub.id)
    job = JobRepository(db).create(session_id=sess.id, subject_id=sub.id)
    sub_id = sub.id
    sess_id = sess.id
    job_id = job.id
    db.close()

    jm = JobManager(db_session_factory=db_factory, max_workers=1)
    jm.submit(
        job_id=job_id,
        task_fn=run_analysis_pipeline,
        recording_path="",
        session_id=sess_id,
        subject_id=sub_id,
    )

    jm.wait_all(timeout=10.0)

    db3 = db_factory()
    j_final = JobRepository(db3).get(job_id)
    db3.close()
    assert j_final.status in ("completed", "partially_completed")
    assert j_final.result_data is not None


def test_job_state_transitions(db_factory):
    db = db_factory()
    sub = SubjectRepository(db).create()
    sess = SessionRepository(db).create(subject_id=sub.id)
    job = JobRepository(db).create(session_id=sess.id, subject_id=sub.id)
    job_id = job.id
    assert job.status == "queued"
    JobRepository(db).update_status(job_id, "running")
    j = JobRepository(db).get(job_id)
    assert j.status == "running"
    JobRepository(db).update_status(job_id, "completed")
    j2 = JobRepository(db).get(job_id)
    assert j2.status == "completed"
    db.close()
