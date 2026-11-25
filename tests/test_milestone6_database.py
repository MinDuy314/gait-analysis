"""Tests for Milestone 6: Database models and repositories."""
import pytest
import tempfile
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.database import Base
from src.database import models  # noqa
from src.database.repositories import SubjectRepository, SessionRepository, RecordingRepository, JobRepository


@pytest.fixture
def db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()
    Path(db_path).unlink(missing_ok=True)


def test_create_subject(db):
    repo = SubjectRepository(db)
    s = repo.create(display_name="Alice")
    assert s.id is not None
    assert s.display_name == "Alice"


def test_get_subject(db):
    repo = SubjectRepository(db)
    s = repo.create()
    fetched = repo.get(s.id)
    assert fetched.id == s.id


def test_soft_delete_subject(db):
    repo = SubjectRepository(db)
    s = repo.create()
    assert repo.soft_delete(s.id)
    assert repo.get(s.id) is None


def test_create_session(db):
    sub = SubjectRepository(db).create()
    sess = SessionRepository(db).create(subject_id=sub.id, camera_view="side")
    assert sess.subject_id == sub.id
    assert sess.camera_view == "side"


def test_list_sessions(db):
    sub = SubjectRepository(db).create()
    for _ in range(3):
        SessionRepository(db).create(subject_id=sub.id)
    sessions = SessionRepository(db).list_for_subject(sub.id)
    assert len(sessions) == 3


def test_create_recording(db):
    sub = SubjectRepository(db).create()
    sess = SessionRepository(db).create(subject_id=sub.id)
    rec = RecordingRepository(db).create(session_id=sess.id, server_filename="abc.mp4", file_path="/data/abc.mp4")
    assert rec.session_id == sess.id


def test_create_job(db):
    sub = SubjectRepository(db).create()
    sess = SessionRepository(db).create(subject_id=sub.id)
    job = JobRepository(db).create(session_id=sess.id, subject_id=sub.id)
    assert job.status == "queued"


def test_job_status_update(db):
    sub = SubjectRepository(db).create()
    sess = SessionRepository(db).create(subject_id=sub.id)
    job = JobRepository(db).create(session_id=sess.id, subject_id=sub.id)
    JobRepository(db).update_status(job.id, "running", stage="estimate_pose", progress=20.0)
    j = JobRepository(db).get(job.id)
    assert j.status == "running"
    assert j.current_stage == "estimate_pose"
    assert j.progress_pct == 20.0
