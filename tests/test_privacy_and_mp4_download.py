import sqlite3
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.dependencies import get_db
from src.api.auth.security import hash_password, create_access_token
from src.core.config import AppConfig
from src.database.database import get_engine, get_session_factory, init_db, Base
from src.database.models import User, Subject, Session as DBSession, Recording, AssessmentRecord, ReportRecord


@pytest.fixture
def client_and_db(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test_privacy.db'}"
    engine = get_engine(db_url)
    Base.metadata.create_all(bind=engine)
    SessionLocal = get_session_factory(db_url)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client, SessionLocal
    app.dependency_overrides.clear()


def _make_user_and_token(db, username: str, role: str, org_id: str | None = "org_a"):
    u = User(
        id=str(uuid.uuid4()),
        username=username,
        hashed_password=hash_password("Pass@123"),
        role=role,
        organization_id=org_id,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    token = create_access_token(data={"sub": u.id, "role": u.role})
    return u, {"Authorization": f"Bearer {token}"}


def test_patient_isolation_and_clinician_org_scoping(client_and_db):
    client, SessionLocal = client_and_db
    with SessionLocal() as db:
        p1, p1_hdr = _make_user_and_token(db, "patient_a", "individual", "org_a")
        p2, p2_hdr = _make_user_and_token(db, "patient_b", "individual", "org_a")
        c_a, ca_hdr = _make_user_and_token(db, "clinician_a", "professional", "org_a")
        c_b, cb_hdr = _make_user_and_token(db, "clinician_b", "professional", "org_b")

        subj_a = Subject(id=str(uuid.uuid4()), display_name="Subj A", owner_id=p1.id, organization_id="org_a")
        subj_b = Subject(id=str(uuid.uuid4()), display_name="Subj B", owner_id=p2.id, organization_id="org_a")
        db.add_all([subj_a, subj_b])
        db.commit()

        sess_b = DBSession(id=str(uuid.uuid4()), subject_id=subj_b.id, camera_view="side")
        db.add(sess_b)
        db.commit()

        assess_b = AssessmentRecord(
            id=str(uuid.uuid4()),
            subject_id=subj_b.id,
            session_id=sess_b.id,
            overall_status="supported",
            assessment_data={"feature_interpretations": [], "reference_comparisons": [{"feature_name": "knee_flexion_rom"}]},
        )
        db.add(assess_b)
        db.commit()

        subj_a_id, subj_b_id, sess_b_id = subj_a.id, subj_b.id, sess_b.id

    # Patient A cannot list Patient B's subject
    res = client.get("/api/v1/subjects", headers=p1_hdr)
    assert res.status_code == 200
    assert [s["id"] for s in res.json()["items"]] == [subj_a_id]

    # Patient A cannot access Patient B's profile, sessions, assessment, or progress
    assert client.get(f"/api/v1/subjects/{subj_b_id}", headers=p1_hdr).status_code == 403
    assert client.get(f"/api/v1/subjects/{subj_b_id}/sessions", headers=p1_hdr).status_code == 403
    assert client.get(f"/api/v1/sessions/{sess_b_id}/assessment", headers=p1_hdr).status_code == 403
    assert client.get(f"/api/v1/subjects/{subj_b_id}/progress", headers=p1_hdr).status_code == 403

    # Patient B cannot generate a clinician-only professional report
    assert client.post(
        f"/api/v1/sessions/{sess_b_id}/reports",
        json={"report_type": "professional"},
        headers=p2_hdr,
    ).status_code == 403

    # Clinician A (org_a) can access Patient B (org_a) and sees reference_comparisons
    res_ca = client.get(f"/api/v1/sessions/{sess_b_id}/assessment", headers=ca_hdr)
    assert res_ca.status_code == 200
    assert "reference_comparisons" in res_ca.json()["data"]

    # Patient B accessing own assessment has reference_comparisons stripped
    res_p2 = client.get(f"/api/v1/sessions/{sess_b_id}/assessment", headers=p2_hdr)
    assert res_p2.status_code == 200
    assert "reference_comparisons" not in res_p2.json()["data"]

    # Clinician B (org_b) cannot access org_a data
    assert client.get(f"/api/v1/subjects/{subj_b_id}", headers=cb_hdr).status_code == 403
    assert client.get(f"/api/v1/sessions/{sess_b_id}/assessment", headers=cb_hdr).status_code == 403


def test_administrator_and_missing_org_fails_securely(client_and_db):
    client, SessionLocal = client_and_db
    with SessionLocal() as db:
        # Admin in org_a
        admin_a, admin_a_hdr = _make_user_and_token(db, "admin_a", "administrator", "org_a")
        # Clinician with no organization
        c_no_org, c_no_org_hdr = _make_user_and_token(db, "c_no_org", "professional", None)

        p, p_hdr = _make_user_and_token(db, "pat_c", "individual", "org_a")
        subj_a = Subject(id=str(uuid.uuid4()), display_name="Subj A", owner_id=p.id, organization_id="org_a")
        subj_b = Subject(id=str(uuid.uuid4()), display_name="Subj B", owner_id=str(uuid.uuid4()), organization_id="org_b")
        subj_no_org = Subject(id=str(uuid.uuid4()), display_name="Subj No Org", owner_id=str(uuid.uuid4()))
        db.add_all([subj_a, subj_b, subj_no_org])
        db.commit()
        from sqlalchemy import text
        db.execute(text("UPDATE users SET organization_id = NULL WHERE id = :uid"), {"uid": c_no_org.id})
        db.execute(text("UPDATE subjects SET organization_id = NULL WHERE id = :sid"), {"sid": subj_no_org.id})
        db.commit()

        subj_a_id = subj_a.id
        subj_b_id = subj_b.id
        subj_no_org_id = subj_no_org.id

    # Admin A can access subject in org_a
    assert client.get(f"/api/v1/subjects/{subj_a_id}", headers=admin_a_hdr).status_code == 200
    # Admin A CANNOT access subject in org_b
    assert client.get(f"/api/v1/subjects/{subj_b_id}", headers=admin_a_hdr).status_code == 403

    # Clinician with missing organization assignment fails securely (403 on subjects)
    assert client.get(f"/api/v1/subjects/{subj_a_id}", headers=c_no_org_hdr).status_code == 403
    # Clinician with missing org gets empty list
    res = client.get("/api/v1/subjects", headers=c_no_org_hdr)
    assert res.status_code == 200
    assert len(res.json()["items"]) == 0

    # Subject with missing organization cannot be accessed by clinician in org_a
    assert client.get(f"/api/v1/subjects/{subj_no_org_id}", headers=admin_a_hdr).status_code == 403


def test_mp4_download_auth_headers_and_errors(client_and_db):
    client, SessionLocal = client_and_db
    cfg = AppConfig()
    ann_dir = (cfg.project_root / "data" / "test_mp4_dl").resolve()
    ann_dir.mkdir(parents=True, exist_ok=True)
    ann_file = ann_dir / "test_annotated.mp4"
    ann_file.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")

    try:
        with SessionLocal() as db:
            p1, p1_hdr = _make_user_and_token(db, "dl_p1", "individual", "org_a")
            _, p2_hdr = _make_user_and_token(db, "dl_p2", "individual", "org_a")
            subj = Subject(id=str(uuid.uuid4()), display_name="DL Subj", owner_id=p1.id, organization_id="org_a")
            db.add(subj)
            db.commit()
            sess = DBSession(id=str(uuid.uuid4()), subject_id=subj.id, camera_view="side")
            db.add(sess)
            db.commit()
            rec = Recording(
                id=str(uuid.uuid4()),
                session_id=sess.id,
                server_filename="test.mp4",
                file_path=str(ann_file),
                annotation_status="completed",
                annotated_video_path=str(ann_file),
            )
            rec_missing = Recording(
                id=str(uuid.uuid4()),
                session_id=sess.id,
                server_filename="missing.mp4",
                file_path=str(ann_dir / "missing.mp4"),
                annotation_status="completed",
                annotated_video_path=str(ann_dir / "missing.mp4"),
            )
            db.add_all([rec, rec_missing])
            db.commit()
            rec_id, rec_missing_id = rec.id, rec_missing.id

        # Unauthenticated request rejected (401)
        assert client.get(f"/api/v1/recordings/{rec_id}/annotated-video").status_code == 401

        # Another patient cannot download (403)
        assert client.get(f"/api/v1/recordings/{rec_id}/annotated-video", headers=p2_hdr).status_code == 403

        # Authorized patient gets actual MP4 bytes with video/mp4 and .mp4 filename
        res = client.get(f"/api/v1/recordings/{rec_id}/annotated-video", headers=p1_hdr)
        assert res.status_code == 200
        assert res.headers["content-type"].startswith("video/mp4")
        assert ".mp4" in res.headers.get("content-disposition", "")
        assert res.content.startswith(b"\x00\x00\x00\x18ftypmp42")

        # Missing file returns 404
        assert client.get(f"/api/v1/recordings/{rec_missing_id}/annotated-video", headers=p1_hdr).status_code == 404
    finally:
        ann_file.unlink(missing_ok=True)
        try:
            ann_dir.rmdir()
        except OSError:
            pass


def test_database_migration_preserves_records_and_is_idempotent(tmp_path):
    """Verify database migration against a pre-existing SQLite database created without organization_id."""
    raw_db_file = tmp_path / "legacy_test.db"
    conn = sqlite3.connect(raw_db_file)
    cur = conn.cursor()

    # Create tables as they existed BEFORE organization_id was added
    cur.execute("""
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            hashed_password TEXT NOT NULL,
            role TEXT DEFAULT 'individual',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE subjects (
            id TEXT PRIMARY KEY,
            display_name TEXT,
            owner_id TEXT,
            is_deleted BOOLEAN DEFAULT 0,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE recordings (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            original_filename TEXT,
            server_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size_bytes INTEGER,
            mime_type TEXT,
            duration_seconds REAL,
            fps REAL,
            width INTEGER,
            height INTEGER,
            validation_status TEXT DEFAULT 'pending',
            validation_message TEXT,
            is_deleted BOOLEAN DEFAULT 0,
            created_at TIMESTAMP
        )
    """)

    # Insert legacy records
    user_id = str(uuid.uuid4())
    subj_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO users (id, username, hashed_password, role) VALUES (?, ?, ?, ?)",
        (user_id, "legacy_user", "hashed_pwd", "individual"),
    )
    cur.execute(
        "INSERT INTO subjects (id, display_name, owner_id) VALUES (?, ?, ?)",
        (subj_id, "Legacy Subject", user_id),
    )
    conn.commit()
    conn.close()

    db_url = f"sqlite:///{raw_db_file}"

    # Run migration first time
    init_db(db_url)

    # Check that legacy records are preserved and backfilled
    SessionLocal = get_session_factory(db_url)
    with SessionLocal() as db:
        u = db.query(User).filter_by(id=user_id).first()
        assert u is not None
        assert u.username == "legacy_user"
        assert u.organization_id == "default_org"

        s = db.query(Subject).filter_by(id=subj_id).first()
        assert s is not None
        assert s.display_name == "Legacy Subject"
        assert s.owner_id == user_id
        assert s.organization_id == "default_org"

    # Run migration a second time (idempotency check)
    init_db(db_url)

    # Verify again that everything remains intact
    with SessionLocal() as db:
        u = db.query(User).filter_by(id=user_id).first()
        assert u is not None
        assert u.username == "legacy_user"
        s = db.query(Subject).filter_by(id=subj_id).first()
        assert s is not None
        assert s.owner_id == user_id
