"""Tests for Milestone 6: Permission model and deletion logging."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.database import Base
from src.database import models
from src.database.models import DeletionLog
from src.database.repositories import SubjectRepository


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    yield db
    db.close()


def test_user_model_has_role(db):
    u = models.User(
        id="u1", username="admin", hashed_password="hashed", role="administrator"
    )
    db.add(u)
    db.commit()
    fetched = db.query(models.User).filter(models.User.id == "u1").first()
    assert fetched.role == "administrator"


def test_soft_delete_logs_deletion(db):
    repo = SubjectRepository(db)
    s = repo.create()
    repo.soft_delete(s.id, deleted_by="admin")
    log = db.query(DeletionLog).filter(DeletionLog.entity_id == s.id).first()
    assert log is not None
    assert log.entity_type == "subject"
    assert log.deleted_by == "admin"


def test_deleted_subject_not_returned(db):
    repo = SubjectRepository(db)
    s = repo.create()
    repo.soft_delete(s.id)
    assert repo.get(s.id) is None
    all_subs = repo.list_all()
    assert all(sub.id != s.id for sub in all_subs)
