from typing import Annotated

from fastapi import APIRouter, Query

from app.core.dependencies import DbSession, PharmacistUser
from app.schemas.prescription import (
    VerificationDecision,
    VerificationDetail,
    VerificationRequestSummary,
)
from app.services import verification_service

router = APIRouter(prefix="/pharmacist", tags=["pharmacist"])


@router.get("/verification-requests", response_model=list[VerificationRequestSummary])
def list_requests(
    _: PharmacistUser,
    db: DbSession,
    status: Annotated[str | None, Query(max_length=40)] = None,
):
    return verification_service.list_requests(db, status)


@router.get("/verification-requests/{prescription_id}", response_model=VerificationDetail)
def get_request(prescription_id: int, _: PharmacistUser, db: DbSession):
    return verification_service.get_request(db, prescription_id)


@router.post("/verification", response_model=VerificationDetail)
def decide(data: VerificationDecision, pharmacist: PharmacistUser, db: DbSession):
    return verification_service.decide(db, pharmacist, data)


@router.get("/history")
def history(pharmacist: PharmacistUser, db: DbSession, mine: bool = False):
    return verification_service.history(db, pharmacist if mine else None)


@router.get("/summary")
def summary(_: PharmacistUser, db: DbSession):
    return {"pending": verification_service.pending_count(db)}
