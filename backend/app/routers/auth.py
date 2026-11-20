from fastapi import APIRouter, Depends, Response, status

from app.core.config import get_settings
from app.core.dependencies import CurrentUser, DbSession
from app.core.rate_limit import RateLimiter
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    ProfileUpdate,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services import audit_service, auth_service

_settings = get_settings()
login_limiter = RateLimiter(_settings.login_rate_limit, _settings.login_rate_window_seconds, "login")
register_limiter = RateLimiter(5, 300, "register")

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(register_limiter)],
)
def register(data: RegisterRequest, db: DbSession):
    user = auth_service.register(db, data)
    return auth_service.build_token_response(user)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(login_limiter)])
def login(data: LoginRequest, db: DbSession):
    user = auth_service.authenticate(db, data.mobile_number, data.password)
    return auth_service.build_token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: DbSession):
    return auth_service.refresh_tokens(db, data.refresh_token)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@router.put("/me", response_model=UserOut)
def update_me(data: ProfileUpdate, user: CurrentUser, db: DbSession):
    return auth_service.update_profile(db, user, data)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(data: ChangePasswordRequest, user: CurrentUser, db: DbSession):
    auth_service.change_password(db, user, data)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: CurrentUser, db: DbSession):
    # Tokens are stateless JWTs; the client discards them. We only keep an audit trail.
    audit_service.record(db, actor_id=user.id, action="user.logout", target_type="user", target_id=user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
