from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import TokenError, decode_token
from app.database.session import SessionLocal
from app.models.user import User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _load_user(db: Session, credentials: HTTPAuthorizationCredentials | None) -> User | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    try:
        payload = decode_token(credentials.credentials, "access")
    except TokenError as exc:
        raise UnauthorizedError(str(exc)) from exc
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise UnauthorizedError("Account no longer exists")
    if not user.is_active:
        raise ForbiddenError("This account has been deactivated")
    return user


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    user = _load_user(db, credentials)
    if user is None:
        raise UnauthorizedError("Authentication required")
    return user


def get_optional_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User | None:
    try:
        return _load_user(db, credentials)
    except (UnauthorizedError, ForbiddenError):
        return None


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_roles(*roles: UserRole):
    allowed = {role.value for role in roles}

    def _dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise ForbiddenError("You do not have permission to perform this action")
        return user

    return _dependency


PharmacistUser = Annotated[User, Depends(require_roles(UserRole.PHARMACIST, UserRole.ADMIN))]
AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
