from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pathlib import Path

class Base(DeclarativeBase):
    pass

_engine = None
_SessionLocal = None

def get_engine(db_url: str = None):
    global _engine
    if _engine is None or db_url is not None:
        if db_url is None:
            from src.core.config import AppConfig
            cfg = AppConfig()
            db_path = cfg.project_root / "data" / "gait_analysis.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{db_path}"
        _engine = create_engine(db_url, connect_args={"check_same_thread": False})
    return _engine

def get_session_factory(db_url: str = None):
    global _SessionLocal
    if _SessionLocal is None or db_url is not None:
        engine = get_engine(db_url)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal

def init_db(db_url: str = None):
    from src.database import models  # noqa
    engine = get_engine(db_url)
    Base.metadata.create_all(bind=engine)

    # Safe migration: add new columns if they don't already exist (SQLite only).
    from sqlalchemy import text
    _migrations = [
        ("recordings", "annotated_video_path TEXT"),
        ("recordings", "annotation_status TEXT DEFAULT 'pending'"),
        ("recordings", "quality_status TEXT"),
        ("recordings", "measurement_confidence REAL"),
        ("recordings", "analysis_warnings TEXT"),
        ("sessions", "session_status TEXT DEFAULT 'active'"),
        ("sessions", "summary TEXT"),
        ("analysis_jobs", "processed_frames INTEGER DEFAULT 0"),
        ("analysis_jobs", "total_frames INTEGER DEFAULT 0"),
        ("assessments", "recording_id TEXT"),
        ("assessments", "clinician_id TEXT"),
        ("assessments", "clinical_interpretation TEXT"),
        ("assessments", "clinical_notes TEXT"),
        ("assessments", "approval_status TEXT DEFAULT 'pending_review'"),
        ("assessments", "approved_by TEXT"),
        ("assessments", "approved_at DATETIME"),
        ("assessments", "updated_at DATETIME"),
        ("reports", "title TEXT"),
        ("reports", "clinician_notes TEXT"),
        ("reports", "rehabilitation_priorities TEXT"),
        ("reports", "recommendations TEXT"),
        ("reports", "report_data TEXT"),
        ("reports", "approved_by TEXT"),
        ("reports", "approved_at DATETIME"),
        ("reports", "published_at DATETIME"),
        ("reports", "revision_history TEXT"),
        ("reports", "updated_at DATETIME"),
    ]
    with engine.connect() as conn:
        for tbl_name, col_def in _migrations:
            try:
                conn.execute(text(f"ALTER TABLE {tbl_name} ADD COLUMN {col_def}"))
                conn.commit()
            except Exception:
                pass  # Column already exists — no action needed.
        for tbl in ("users", "subjects"):
            try:
                conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN organization_id TEXT DEFAULT 'default_org'"))
                conn.commit()
            except Exception:
                pass
            try:
                conn.execute(text(f"UPDATE {tbl} SET organization_id = 'default_org' WHERE organization_id IS NULL"))
                conn.commit()
            except Exception:
                pass

    # Seed default demonstration accounts if no users exist
    from src.database.models import User
    from src.api.auth.security import hash_password
    import uuid
    from datetime import datetime
    Session = get_session_factory(db_url)
    with Session() as sess:
        if sess.query(User).count() == 0:
            clinician = User(
                id=str(uuid.uuid4()),
                username="dr_smith",
                email="dr.smith@biomechanics.org",
                hashed_password=hash_password("Clinician@123"),
                role="professional",
                is_active=True,
                created_at=datetime.utcnow(),
            )
            patient = User(
                id=str(uuid.uuid4()),
                username="patient_john",
                email="john.patient@example.com",
                hashed_password=hash_password("Patient@123"),
                role="individual",
                is_active=True,
                created_at=datetime.utcnow(),
            )
            sess.add_all([clinician, patient])
            sess.commit()

    return engine
