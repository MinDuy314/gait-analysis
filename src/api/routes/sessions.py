from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.api.schemas.api_responses import SessionResponse, PaginatedResponse
from src.api.schemas.requests import SessionCreate
from src.database.repositories import SessionRepository, SubjectRepository

router = APIRouter(tags=["sessions"])


@router.post("/api/v1/subjects/{subject_id}/sessions", response_model=SessionResponse, status_code=201)
def create_session(subject_id: str, payload: SessionCreate, db: Session = Depends(get_db)):
    subject = SubjectRepository(db).get(subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    repo = SessionRepository(db)
    s = repo.create(subject_id=subject_id, **payload.model_dump(exclude_none=True))
    return s


@router.get("/api/v1/subjects/{subject_id}/sessions", response_model=PaginatedResponse[SessionResponse])
def list_sessions(subject_id: str, skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    subject = SubjectRepository(db).get(subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    items = SessionRepository(db).list_for_subject(subject_id, skip, limit)
    return {"items": items, "total": len(items), "skip": skip, "limit": limit}


@router.get("/api/v1/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, db: Session = Depends(get_db)):
    s = SessionRepository(db).get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return s
