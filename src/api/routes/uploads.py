import tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from src.api.dependencies import get_db, get_storage
from src.api.auth.dependencies import get_current_user, verify_subject_access
from src.api.schemas.api_responses import RecordingResponse
from src.database.models import User
from src.database.repositories import RecordingRepository, SessionRepository, SubjectRepository
from src.storage.file_storage import ALLOWED_EXTENSIONS
from src.core.logging import get_logger
from src.core.config import AppConfig

logger = get_logger(__name__)
router = APIRouter(tags=["recordings"])


@router.post("/api/v1/sessions/{session_id}/recordings", response_model=RecordingResponse, status_code=201)
async def upload_recording(
    session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
    current_user: User = Depends(get_current_user),
):
    sess = SessionRepository(db).get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    subj = SubjectRepository(db).get(sess.subject_id)
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(subj, current_user)

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}. Allowed: {ALLOWED_EXTENSIONS}")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        try:
            while chunk := await file.read(1024 * 1024):
                tmp.write(chunk)
        except Exception as e:
            tmp_path.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    try:
        server_name, final_path, size = storage.save_upload(
            source_path=tmp_path,
            original_filename=file.filename or "upload",
            subject_id=sess.subject_id,
            session_id=session_id,
        )
    except ValueError as e:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))

    rec = RecordingRepository(db).create(
        session_id=session_id,
        server_filename=server_name,
        file_path=str(final_path),
        original_filename=file.filename,
        file_size_bytes=size,
        mime_type=file.content_type,
        validation_status="pending",
    )
    return rec


@router.get("/api/v1/sessions/{session_id}/recordings", response_model=list[RecordingResponse])
def list_recordings(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sess = SessionRepository(db).get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    subj = SubjectRepository(db).get(sess.subject_id)
    if not subj:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(subj, current_user)
    return RecordingRepository(db).list_for_session(session_id)


@router.get("/api/v1/recordings/{recording_id}", response_model=RecordingResponse)
def get_recording(
    recording_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = RecordingRepository(db).get(recording_id)
    if not r:
        raise HTTPException(status_code=404, detail="Recording not found")
    sess = SessionRepository(db).get(r.session_id)
    if sess:
        subj = SubjectRepository(db).get(sess.subject_id)
        if subj:
            verify_subject_access(subj, current_user)
    return r


@router.get(
    "/api/v1/recordings/{recording_id}/annotated-video",
    summary="Stream annotated video (MP4)",
)
def get_annotated_video(
    recording_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream the annotated MP4 for a completed recording.

    - 404: recording not found, or file missing despite completed status.
    - 409: annotation not yet completed (pending / failed / not_applicable).
    """
    from fastapi.responses import FileResponse as _FR
    from src.core.config import AppConfig

    r = RecordingRepository(db).get(recording_id)
    if not r:
        raise HTTPException(status_code=404, detail="Recording not found")
    sess = SessionRepository(db).get(r.session_id)
    if sess:
        subj = SubjectRepository(db).get(sess.subject_id)
        if subj:
            verify_subject_access(subj, current_user)

    if r.annotation_status != "completed":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Annotated video not ready. Current annotation_status: "
                f"{r.annotation_status or 'pending'}"
            ),
        )

    if not r.annotated_video_path:
        raise HTTPException(status_code=404, detail="Annotated video path not recorded")

    # Path traversal protection
    ann_path = Path(r.annotated_video_path).resolve()
    cfg = AppConfig()
    storage_root = (cfg.project_root / "data").resolve()
    try:
        ann_path.relative_to(storage_root)
    except ValueError:
        logger.warning(
            "Annotated video path %s is outside storage root %s",
            ann_path, storage_root,
        )
        raise HTTPException(status_code=403, detail="Annotated video path is not accessible")

    if not ann_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Annotated video file not found on disk",
        )

    dl_name = ann_path.name if ann_path.name.lower().endswith(".mp4") else f"annotated_{recording_id}.mp4"
    return _FR(
        path=str(ann_path),
        media_type="video/mp4",
        filename=dl_name,
    )
