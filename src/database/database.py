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
    _new_cols = [
        "annotated_video_path TEXT",
        "annotation_status TEXT DEFAULT 'pending'",
    ]
    with engine.connect() as conn:
        for col_def in _new_cols:
            try:
                conn.execute(text(f"ALTER TABLE recordings ADD COLUMN {col_def}"))
                conn.commit()
            except Exception:
                pass  # Column already exists — no action needed.

    return engine
