from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.catalogue import ProductOut, only_active_products
from app.schemas.common import ORMModel

HANDWRITING_DISCLAIMER = (
    "IMPORTANT: Handwritten prescription recognition may incorrectly identify medicine names, "
    "strengths or dosage information because of unclear handwriting, medical abbreviations and "
    "similar-looking words. AI-extracted information is only an interpretation of the uploaded "
    "image and is not a confirmed prescription. Always compare extracted details against the "
    "original prescription. Unclear or uncertain information requires pharmacist verification. "
    "Never use OCR or AI-generated results alone to decide which medicine to take."
)


class MedicineRef(ORMModel):
    id: int
    medicine_name: str
    generic_name: str | None
    brand_name: str | None
    strength: str | None
    formulation: str | None
    prescription_required: bool
    composition: str | None = None
    image_url: str | None
    products: list[ProductOut]

    _active_products = field_validator("products", mode="before")(only_active_products)


class CandidateOut(BaseModel):
    medicine_id: int
    medicine_name: str
    brand_name: str | None
    generic_name: str | None
    strength: str | None
    formulation: str | None
    prescription_required: bool
    score: float
    matched_on: str


class PrescriptionItemOut(ORMModel):
    id: int
    extracted_name: str
    original_text: str | None
    strength_text: str | None
    formulation_text: str | None
    dosage_text: str | None
    frequency_text: str | None
    duration_text: str | None
    uncertainty_status: str
    uncertain_fields: list[str] = []
    match_status: str
    matched_medicine: MedicineRef | None
    candidates: list[CandidateOut] = []
    user_confirmed: bool
    user_edited: bool
    included: bool
    can_add_to_cart: bool = False
    blocked_reason: str | None = None

    @field_validator("uncertain_fields", "candidates", mode="before")
    @classmethod
    def _none_to_list(cls, value):
        return [] if value is None else value


class VerificationOut(ORMModel):
    id: int
    verification_status: str
    notes: str | None
    verified_at: datetime
    pharmacist_name: str | None = None


class PrescriptionOut(ORMModel):
    id: int
    processing_status: str
    document_type: str
    source_format: str
    page_count: int
    ocr_engine: str | None
    ocr_confidence: float | None
    ai_review_status: str
    ai_model: str | None
    user_confirmation_status: str
    pharmacist_verification_status: str
    customer_notes: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
    items: list[PrescriptionItemOut]
    verifications: list[VerificationOut] = []
    warnings: list[str] = []
    show_handwriting_disclaimer: bool = False
    handwriting_disclaimer: str | None = None
    original_image_retained: bool = False


class ProcessingInfo(BaseModel):
    ocr_engine: str | None
    ocr_available: bool
    handwriting_engine_used: bool
    ai_source: str
    elapsed_ms: int
    preprocessing_steps: list[str]
    notes: list[str] = []


class AnalyseResponse(BaseModel):
    prescription: PrescriptionOut
    extracted_text: str
    preview_images: list[str]
    processing: ProcessingInfo


class ConfirmItemIn(BaseModel):
    item_id: int
    extracted_name: str = Field(min_length=1, max_length=200)
    strength_text: str | None = Field(default=None, max_length=100)
    formulation_text: str | None = Field(default=None, max_length=100)
    dosage_text: str | None = Field(default=None, max_length=200)
    frequency_text: str | None = Field(default=None, max_length=200)
    duration_text: str | None = Field(default=None, max_length=200)
    matched_medicine_id: int | None = None
    included: bool = True

    @field_validator(
        "strength_text",
        "formulation_text",
        "dosage_text",
        "frequency_text",
        "duration_text",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value


class NewItemIn(BaseModel):
    extracted_name: str = Field(min_length=1, max_length=200)
    strength_text: str | None = Field(default=None, max_length=100)
    formulation_text: str | None = Field(default=None, max_length=100)
    dosage_text: str | None = Field(default=None, max_length=200)
    frequency_text: str | None = Field(default=None, max_length=200)
    duration_text: str | None = Field(default=None, max_length=200)
    matched_medicine_id: int | None = None

    @field_validator(
        "strength_text",
        "formulation_text",
        "dosage_text",
        "frequency_text",
        "duration_text",
        mode="before",
    )
    @classmethod
    def _blank_to_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value


class ConfirmRequest(BaseModel):
    prescription_id: int
    items: list[ConfirmItemIn] = Field(default_factory=list)
    new_items: list[NewItemIn] = Field(default_factory=list, max_length=20)
    customer_notes: str | None = Field(default=None, max_length=1000)
    request_pharmacist_review: bool = False
    add_to_cart: bool = True


class CartAddition(BaseModel):
    medicine_name: str
    product_id: int
    pack_size: str
    quantity: int


class CartSkip(BaseModel):
    name: str
    reason: str


class ReviewRequest(BaseModel):
    message: str | None = Field(default=None, max_length=1000)


class PrescriptionListItem(ORMModel):
    id: int
    processing_status: str
    document_type: str
    user_confirmation_status: str
    pharmacist_verification_status: str
    ai_review_status: str
    created_at: datetime
    item_count: int = 0


class VerificationRequestSummary(BaseModel):
    prescription_id: int
    customer_name: str
    customer_mobile_masked: str
    document_type: str
    ai_review_status: str
    ocr_confidence: float | None
    user_confirmation_status: str
    pharmacist_verification_status: str
    item_count: int
    rx_item_count: int
    uncertain_item_count: int
    customer_notes: str | None
    created_at: datetime
    updated_at: datetime


class VerificationDetail(PrescriptionOut):
    customer_name: str
    customer_mobile_masked: str
    extracted_text: str | None
    linked_order_numbers: list[str] = []


class VerificationDecision(BaseModel):
    prescription_id: int
    status: Literal["approved", "rejected", "clarification_requested"]
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("notes", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class ConfirmResponse(PrescriptionOut):
    cart_added: list[CartAddition] = []
    cart_skipped: list[CartSkip] = []
