import tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from src.api.dependencies import get_db, get_storage
from src.api.schemas.api_responses import RecordingResponse
from src.database.repositories import RecordingRepository, SessionRepository
from src.storage.file_storage import ALLOWED_EXTENSIONS
from src.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["recordings"])


@router.post("/api/v1/sessions/{session_id}/recordings", response_model=RecordingResponse, status_code=201)
async def upload_recording(
    session_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage=Depends(get_storage),
):
    sess = SessionRepository(db).get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

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
def list_recordings(session_id: str, db: Session = Depends(get_db)):
    sess = SessionRepository(db).get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return RecordingRepository(db).list_for_session(session_id)


@router.get("/api/v1/recordings/{recording_id}", response_model=RecordingResponse)
def get_recording(recording_id: str, db: Session = Depends(get_db)):
    r = RecordingRepository(db).get(recording_id)
    if not r:
        raise HTTPException(status_code=404, detail="Recording not found")
    return r
