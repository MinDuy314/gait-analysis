"""FastAPI dependencies for authentication."""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session
from src.api.dependencies import get_db
from src.api.auth.security import decode_token
from src.database.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise credentials_exception
    return user


def get_optional_user(
    db: Session = Depends(get_db),
    token: str = Depends(OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)),
) -> User | None:
    """Return current user if token is valid, else None (for optional-auth endpoints)."""
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            return None
        return db.query(User).filter(User.id == user_id, User.is_active == True).first()
    except JWTError:
        return None


def require_role(*roles: str):
    """Dependency factory that enforces one of the given roles."""
    def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return _check


def verify_subject_access(subject, current_user: User) -> None:
    """Enforce patient ownership and clinician/admin organization-scoped access."""
    if current_user.role == "individual":
        if not subject.owner_id or subject.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to access this subject")
    elif current_user.role in ("professional", "administrator"):
        user_org = getattr(current_user, "organization_id", None)
        subj_org = getattr(subject, "organization_id", None)
        if not user_org or not subj_org or user_org != subj_org:
            raise HTTPException(status_code=403, detail="Not authorized: organization assignment missing or mismatched")
    else:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
