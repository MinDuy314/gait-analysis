from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.api.auth.dependencies import get_current_user, verify_subject_access
from src.api.schemas.api_responses import SubjectResponse, PaginatedResponse
from src.api.schemas.requests import SubjectCreate, SubjectUpdate
from src.database.models import Subject, User
from src.database.repositories import SubjectRepository

router = APIRouter(prefix="/api/v1/subjects", tags=["subjects"])


@router.post("", response_model=SubjectResponse, status_code=201)
def create_subject(
    payload: SubjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SubjectRepository(db)
    subject = repo.create(display_name=payload.display_name, owner_id=current_user.id)
    subject.organization_id = current_user.organization_id
    db.commit()
    db.refresh(subject)
    return subject


@router.get("", response_model=PaginatedResponse[SubjectResponse])
def list_subjects(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Subject).filter(Subject.is_deleted == False)
    if current_user.role == "individual":
        q = q.filter(Subject.owner_id == current_user.id)
    elif current_user.role in ("professional", "administrator"):
        if not current_user.organization_id:
            return {"items": [], "total": 0, "skip": skip, "limit": limit}
        q = q.filter(Subject.organization_id == current_user.organization_id)
    else:
        return {"items": [], "total": 0, "skip": skip, "limit": limit}
    items = q.offset(skip).limit(limit).all()
    return {"items": items, "total": len(items), "skip": skip, "limit": limit}


@router.get("/{subject_id}", response_model=SubjectResponse)
def get_subject(
    subject_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SubjectRepository(db)
    s = repo.get(subject_id)
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(s, current_user)
    return s


@router.patch("/{subject_id}", response_model=SubjectResponse)
def update_subject(
    subject_id: str,
    payload: SubjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SubjectRepository(db)
    s = repo.get(subject_id)
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(s, current_user)
    if payload.display_name is not None:
        s.display_name = payload.display_name
        db.commit()
        db.refresh(s)
    return s


@router.delete("/{subject_id}", status_code=204)
def delete_subject(
    subject_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SubjectRepository(db)
    s = repo.get(subject_id)
    if not s:
        raise HTTPException(status_code=404, detail="Subject not found")
    verify_subject_access(s, current_user)
    repo.soft_delete(subject_id)
