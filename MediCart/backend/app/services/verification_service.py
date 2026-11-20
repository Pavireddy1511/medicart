from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ConflictError, ValidationError
from app.models.enums import UserConfirmationStatus, VerificationStatus
from app.models.order import Order
from app.models.prescription import PharmacistVerification, Prescription, PrescriptionItem
from app.models.user import User
from app.schemas.prescription import (
    VerificationDecision,
    VerificationDetail,
    VerificationOut,
    VerificationRequestSummary,
)
from app.services import audit_service, order_service
from app.services.prescription_service import get_prescription, to_out
from app.utils.text import mask_mobile

OPEN_STATUSES = {
    VerificationStatus.PENDING.value,
    VerificationStatus.CLARIFICATION_REQUESTED.value,
}


def list_requests(db: Session, status: str | None = None) -> list[VerificationRequestSummary]:
    stmt = (
        select(Prescription)
        .options(
            selectinload(Prescription.items).selectinload(PrescriptionItem.matched_medicine),
            selectinload(Prescription.user),
        )
        .where(Prescription.user_confirmation_status == UserConfirmationStatus.CONFIRMED.value)
    )
    if status == "all":
        stmt = stmt.where(
            Prescription.pharmacist_verification_status != VerificationStatus.NOT_REQUIRED.value
        )
    elif status:
        stmt = stmt.where(Prescription.pharmacist_verification_status == status)
    else:
        stmt = stmt.where(Prescription.pharmacist_verification_status.in_(OPEN_STATUSES))
    stmt = stmt.order_by(Prescription.updated_at.asc() if not status else Prescription.updated_at.desc())

    summaries = []
    for prescription in db.scalars(stmt).all():
        included = [i for i in prescription.items if i.included]
        summaries.append(
            VerificationRequestSummary(
                prescription_id=prescription.id,
                customer_name=prescription.user.full_name,
                customer_mobile_masked=mask_mobile(prescription.user.mobile_number),
                document_type=prescription.document_type,
                ai_review_status=prescription.ai_review_status,
                ocr_confidence=float(prescription.ocr_confidence)
                if prescription.ocr_confidence is not None
                else None,
                user_confirmation_status=prescription.user_confirmation_status,
                pharmacist_verification_status=prescription.pharmacist_verification_status,
                item_count=len(included),
                rx_item_count=sum(
                    1 for i in included if i.matched_medicine and i.matched_medicine.prescription_required
                ),
                uncertain_item_count=sum(1 for i in included if i.uncertainty_status == "uncertain"),
                customer_notes=prescription.customer_notes,
                created_at=prescription.created_at,
                updated_at=prescription.updated_at,
            )
        )
    return summaries


def get_request(db: Session, prescription_id: int) -> VerificationDetail:
    prescription = get_prescription(db, prescription_id)
    base = to_out(prescription)
    orders = db.scalars(select(Order.order_number).where(Order.prescription_id == prescription.id)).all()
    return VerificationDetail(
        **base.model_dump(),
        customer_name=prescription.user.full_name,
        customer_mobile_masked=mask_mobile(prescription.user.mobile_number),
        extracted_text=prescription.extracted_text,
        linked_order_numbers=list(orders),
    )


def decide(db: Session, pharmacist: User, decision: VerificationDecision) -> VerificationDetail:
    prescription = get_prescription(db, decision.prescription_id)
    if prescription.user_confirmation_status != UserConfirmationStatus.CONFIRMED.value:
        raise ConflictError("The customer has not confirmed this prescription yet", code="unconfirmed")
    if prescription.pharmacist_verification_status not in OPEN_STATUSES:
        raise ConflictError(
            f"This prescription is already '{prescription.pharmacist_verification_status}'",
            code="already_decided",
        )
    if decision.status in {"rejected", "clarification_requested"} and not decision.notes:
        raise ValidationError("Please add a note explaining the decision", code="notes_required")

    prescription.pharmacist_verification_status = decision.status
    prescription.verifications.append(
        PharmacistVerification(
            pharmacist_id=pharmacist.id,
            verification_status=decision.status,
            notes=decision.notes,
        )
    )
    affected = 0
    if decision.status in {"approved", "rejected"}:
        affected = order_service.apply_prescription_decision(
            db, prescription, approved=decision.status == "approved"
        )
    audit_service.record(
        db,
        actor_id=pharmacist.id,
        action=f"prescription.{decision.status}",
        target_type="prescription",
        target_id=prescription.id,
        meta={"orders_updated": affected},
    )
    db.commit()
    return get_request(db, prescription.id)


def history(db: Session, pharmacist: User | None = None, limit: int = 100) -> list[dict]:
    stmt = (
        select(PharmacistVerification)
        .options(selectinload(PharmacistVerification.pharmacist))
        .order_by(PharmacistVerification.verified_at.desc())
        .limit(limit)
    )
    if pharmacist is not None:
        stmt = stmt.where(PharmacistVerification.pharmacist_id == pharmacist.id)
    rows = db.scalars(stmt).all()
    return [
        {
            **VerificationOut(
                id=v.id,
                verification_status=v.verification_status,
                notes=v.notes,
                verified_at=v.verified_at,
                pharmacist_name=v.pharmacist.full_name if v.pharmacist else None,
            ).model_dump(),
            "prescription_id": v.prescription_id,
        }
        for v in rows
    ]


def pending_count(db: Session) -> int:
    return int(
        db.scalar(
            select(func.count(Prescription.id)).where(
                Prescription.pharmacist_verification_status.in_(OPEN_STATUSES)
            )
        )
        or 0
    )
