from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.base import TimestampMixin
from app.models.catalogue import Medicine
from app.models.enums import (
    AIReviewStatus,
    DocumentType,
    MatchStatus,
    ProcessingStatus,
    SourceFormat,
    UncertaintyStatus,
    UserConfirmationStatus,
    VerificationStatus,
)
from app.models.user import User


class Prescription(TimestampMixin, Base):
    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    processing_status: Mapped[str] = mapped_column(
        String(30), default=ProcessingStatus.PROCESSING.value, nullable=False
    )
    document_type: Mapped[str] = mapped_column(
        String(20), default=DocumentType.UNKNOWN.value, nullable=False
    )
    source_format: Mapped[str] = mapped_column(
        String(10), default=SourceFormat.IMAGE.value, nullable=False
    )
    page_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_engine: Mapped[str | None] = mapped_column(String(30), nullable=True)
    ocr_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    ai_review_status: Mapped[str] = mapped_column(
        String(30), default=AIReviewStatus.SKIPPED.value, nullable=False
    )
    ai_model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    user_confirmation_status: Mapped[str] = mapped_column(
        String(20), default=UserConfirmationStatus.PENDING.value, nullable=False, index=True
    )
    pharmacist_verification_status: Mapped[str] = mapped_column(
        String(30), default=VerificationStatus.NOT_REQUIRED.value, nullable=False, index=True
    )
    customer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship()
    items: Mapped[list["PrescriptionItem"]] = relationship(
        back_populates="prescription", cascade="all, delete-orphan", order_by="PrescriptionItem.id"
    )
    verifications: Mapped[list["PharmacistVerification"]] = relationship(
        back_populates="prescription",
        cascade="all, delete-orphan",
        order_by="PharmacistVerification.verified_at.desc()",
    )


class PrescriptionItem(TimestampMixin, Base):
    __tablename__ = "prescription_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    prescription_id: Mapped[int] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    extracted_name: Mapped[str] = mapped_column(String(200), nullable=False)
    original_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    matched_medicine_id: Mapped[int | None] = mapped_column(
        ForeignKey("medicines.id", ondelete="SET NULL"), nullable=True
    )
    match_status: Mapped[str] = mapped_column(
        String(20), default=MatchStatus.NONE.value, nullable=False
    )
    candidates: Mapped[list | None] = mapped_column(JSON, nullable=True)
    strength_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    formulation_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dosage_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    frequency_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    duration_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    uncertainty_status: Mapped[str] = mapped_column(
        String(20), default=UncertaintyStatus.UNCERTAIN.value, nullable=False
    )
    uncertain_fields: Mapped[list | None] = mapped_column(JSON, nullable=True)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    user_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    included: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    prescription: Mapped[Prescription] = relationship(back_populates="items")
    matched_medicine: Mapped[Medicine | None] = relationship()


class PharmacistVerification(Base):
    __tablename__ = "pharmacist_verifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    prescription_id: Mapped[int] = mapped_column(
        ForeignKey("prescriptions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    pharmacist_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    prescription: Mapped[Prescription] = relationship(back_populates="verifications")
    pharmacist: Mapped[User | None] = relationship()
