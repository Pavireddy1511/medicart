from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.core.config import get_settings
from app.core.dependencies import CurrentUser, DbSession, SettingsDep
from app.core.rate_limit import RateLimiter
from app.schemas.prescription import (
    AnalyseResponse,
    ConfirmRequest,
    ConfirmResponse,
    PrescriptionListItem,
    PrescriptionOut,
    ReviewRequest,
)
from app.services import prescription_service

_settings = get_settings()
analyse_limiter = RateLimiter(_settings.analyse_rate_limit, _settings.analyse_rate_window_seconds, "analyse")

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])


@router.post(
    "/analyse",
    response_model=AnalyseResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(analyse_limiter)],
)
async def analyse(
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    file: Annotated[UploadFile, File(description="JPG, PNG or PDF prescription")],
    document_type: Annotated[str | None, Form()] = None,
):
    return await prescription_service.analyse(db, user, file, document_type, settings)


@router.post("/confirm", response_model=ConfirmResponse)
def confirm(data: ConfirmRequest, user: CurrentUser, db: DbSession):
    return prescription_service.confirm(db, user, data)


@router.get("", response_model=list[PrescriptionListItem])
def list_prescriptions(user: CurrentUser, db: DbSession):
    return prescription_service.list_prescriptions(db, user)


@router.get("/{prescription_id}", response_model=PrescriptionOut)
def get_prescription(prescription_id: int, user: CurrentUser, db: DbSession):
    return prescription_service.to_out(prescription_service.get_prescription(db, prescription_id, user))


@router.get("/{prescription_id}/status", response_model=PrescriptionOut)
def get_status(prescription_id: int, user: CurrentUser, db: DbSession):
    return prescription_service.to_out(prescription_service.get_prescription(db, prescription_id, user))


@router.post("/{prescription_id}/request-review", response_model=PrescriptionOut)
def request_review(prescription_id: int, data: ReviewRequest, user: CurrentUser, db: DbSession):
    return prescription_service.request_review(db, user, prescription_id, data)
