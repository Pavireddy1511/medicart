import logging
import time
from decimal import Decimal

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.ai.groq_client import GroqUnavailable
from app.ai.structuring import structure_prescription
from app.ai.vision import transcribe_with_groq_vision
from app.computer_vision.documents import encode_preview, load_document, read_upload, sniff_format
from app.computer_vision.ocr import OCRLine, get_engine, get_handwriting_engine
from app.computer_vision.preprocessing import preprocess
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError, ConflictError, NotFoundError, ValidationError
from app.models.catalogue import Medicine, Product
from app.models.enums import (
    AIReviewStatus,
    DocumentType,
    MatchStatus,
    ProcessingStatus,
    UncertaintyStatus,
    UserConfirmationStatus,
    VerificationStatus,
)
from app.models.prescription import Prescription, PrescriptionItem
from app.models.user import User
from app.schemas.prescription import (
    HANDWRITING_DISCLAIMER,
    AnalyseResponse,
    ConfirmRequest,
    ConfirmResponse,
    PrescriptionItemOut,
    PrescriptionListItem,
    PrescriptionOut,
    ProcessingInfo,
    ReviewRequest,
    VerificationOut,
)
from app.services import audit_service, cart_service
from app.services.matching_service import match_in_db
from app.utils.text import extract_strength

logger = logging.getLogger(__name__)

MAX_STORED_TEXT = 6000
MAX_ITEMS = 25


def _prescription_query():
    return select(Prescription).options(
        selectinload(Prescription.items)
        .selectinload(PrescriptionItem.matched_medicine)
        .selectinload(Medicine.products)
        .selectinload(Product.inventory),
        selectinload(Prescription.verifications),
    )


def get_prescription(db: Session, prescription_id: int, user: User | None = None) -> Prescription:
    stmt = _prescription_query().where(Prescription.id == prescription_id)
    if user is not None:
        stmt = stmt.where(Prescription.user_id == user.id)
    prescription = db.scalar(stmt)
    if prescription is None:
        raise NotFoundError("Prescription not found")
    return prescription


def list_prescriptions(db: Session, user: User) -> list[PrescriptionListItem]:
    counts = (
        select(PrescriptionItem.prescription_id, func.count(PrescriptionItem.id).label("n"))
        .group_by(PrescriptionItem.prescription_id)
        .subquery()
    )
    rows = db.execute(
        select(Prescription, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.prescription_id == Prescription.id)
        .where(Prescription.user_id == user.id)
        .order_by(Prescription.created_at.desc(), Prescription.id.desc())
    ).all()
    result = []
    for prescription, count in rows:
        item = PrescriptionListItem.model_validate(prescription)
        item.item_count = int(count)
        result.append(item)
    return result


def _classify_document(
    hint: str | None, handwriting_scores: list[float], confidence: float | None
) -> DocumentType:
    if hint in {DocumentType.PRINTED.value, DocumentType.HANDWRITTEN.value}:
        return DocumentType(hint)
    score = sum(handwriting_scores) / len(handwriting_scores) if handwriting_scores else 0.5
    if score > 0.6 or (confidence is not None and confidence < 0.65):
        return DocumentType.HANDWRITTEN
    if score < 0.45 and (confidence is None or confidence >= 0.82):
        return DocumentType.PRINTED
    return DocumentType.UNKNOWN


async def analyse(
    db: Session, user: User, upload: UploadFile, document_hint: str | None, settings: Settings
) -> AnalyseResponse:
    started = time.perf_counter()
    data = await read_upload(upload, settings.max_upload_bytes)
    source_format = sniff_format(data, upload.filename, upload.content_type)
    document = load_document(data, source_format, settings.max_pdf_pages)
    del data

    engine = get_engine(settings)
    notes: list[str] = []
    previews: list[str] = []
    lines: list[OCRLine] = []
    steps: list[str] = []
    handwriting_scores: list[float] = []
    enhanced_pages = []

    for page in document.pages:
        pre = preprocess(page)
        previews.append(encode_preview(pre.original))
        handwriting_scores.append(pre.handwriting_score)
        enhanced_pages.append(pre)
        for step in pre.steps:
            if step not in steps:
                steps.append(step)
        if engine is not None:
            source = pre.binary if engine.name == "tesseract" else pre.enhanced
            try:
                result = engine.recognise(source)
                lines.extend(result.lines)
            except Exception:  # noqa: BLE001
                logger.exception("OCR engine %s failed", engine.name)
                notes.append("The OCR engine failed on this document. You can type the medicines manually.")

    if document.total_pages > len(document.pages):
        notes.append(
            f"Only the first {len(document.pages)} of {document.total_pages} PDF pages were processed."
        )
    if engine is None:
        notes.append("No OCR engine is installed on this server. Enter the medicines manually below.")

    confidence = None
    confidences = [line.confidence for line in lines if line.confidence is not None]
    if confidences:
        confidence = sum(confidences) / len(confidences)

    document_type = _classify_document(document_hint, handwriting_scores, confidence)
    handwriting_used = False
    read_with: str | None = None
    no_text = not any(line.text.strip() for line in lines)
    clearly_printed = document_type == DocumentType.PRINTED and confidence is not None and confidence >= 0.9
    if settings.groq_vision_configured and enhanced_pages and (no_text or not clearly_printed):
        try:
            vision_lines: list[OCRLine] = []
            vision_model = None
            for pre in enhanced_pages:
                page_lines, _meta, vision_model = transcribe_with_groq_vision(pre.original, settings)
                vision_lines.extend(OCRLine(text=text) for text in page_lines)
            if vision_lines:
                lines = vision_lines
                confidence = None
                read_with = "groq-vision"
                notes.append(
                    f"The page was transcribed by the vision model ({vision_model}). "
                    "Treat it as a draft and check every line against the paper copy."
                )
        except GroqUnavailable as exc:
            logger.warning("Groq vision unavailable (%s): %s", exc.reason, exc.message)
            notes.append(f"Vision transcription unavailable ({exc.message}); OCR output is shown instead.")
    if document_type == DocumentType.HANDWRITTEN and read_with is None:
        handwriting_engine = get_handwriting_engine(settings)
        if handwriting_engine is not None and enhanced_pages:
            try:
                hw_lines: list[OCRLine] = []
                for pre in enhanced_pages:
                    boxes = [line.box for line in lines if line.box] or None
                    hw_lines.extend(handwriting_engine.recognise(pre.enhanced, boxes).lines)
                if hw_lines:
                    lines = hw_lines
                    handwriting_used = True
                    hw_conf = [line.confidence for line in hw_lines if line.confidence is not None]
                    confidence = sum(hw_conf) / len(hw_conf) if hw_conf else confidence
            except Exception:  # noqa: BLE001
                logger.exception("Handwriting engine failed")
                notes.append("The handwriting model failed; printed-text OCR output is shown instead.")
        else:
            notes.append(
                "This looks handwritten. The experimental handwriting model is not enabled, so "
                "printed-text OCR output is shown and may be unreliable."
            )

    text_lines = [line.text for line in lines if line.text.strip()]
    ocr_text = "\n".join(text_lines)
    structuring = structure_prescription(
        ocr_text, text_lines, settings, handwritten=document_type == DocumentType.HANDWRITTEN
    )
    notes.extend(structuring.messages)

    ai_status = {
        "groq": AIReviewStatus.COMPLETED,
        "fallback": AIReviewStatus.FALLBACK,
        "unavailable": AIReviewStatus.UNAVAILABLE,
        "skipped": AIReviewStatus.SKIPPED,
    }[structuring.source]

    engine_name = read_with or ("trocr" if handwriting_used else (engine.name if engine else None))
    prescription = Prescription(
        user_id=user.id,
        processing_status=ProcessingStatus.COMPLETED.value,
        document_type=document_type.value,
        source_format=source_format.value,
        page_count=len(document.pages),
        extracted_text=ocr_text[:MAX_STORED_TEXT] if ocr_text else None,
        ocr_engine=engine_name,
        ocr_confidence=Decimal(str(round(confidence, 4))) if confidence is not None else None,
        ai_review_status=ai_status.value,
        ai_model=structuring.model,
        user_confirmation_status=UserConfirmationStatus.PENDING.value,
        pharmacist_verification_status=VerificationStatus.NOT_REQUIRED.value,
    )

    for med in structuring.result.medicines[:MAX_ITEMS]:
        outcome = match_in_db(db, med.extracted_name, med.composition, med.strength, med.formulation)
        if (
            document_type == DocumentType.HANDWRITTEN
            and outcome.status == MatchStatus.NONE
            and not outcome.candidates
            and extract_strength(med.original_text or "") is None
        ):
            # lenient handwriting mode produces noise; keep only lines that resemble something we sell
            continue
        original = med.original_text or ""
        if med.composition:
            original = f"{original} / {med.composition}".strip(" /")
        uncertain = list(dict.fromkeys(med.uncertain_fields))
        if outcome.status in {MatchStatus.UNCERTAIN, MatchStatus.NONE} and "match" not in uncertain:
            uncertain.append("match")
        prescription.items.append(
            PrescriptionItem(
                extracted_name=med.extracted_name[:200],
                original_text=original[:500] or None,
                matched_medicine_id=outcome.medicine_id,
                match_status=outcome.status.value,
                candidates=outcome.candidates,
                strength_text=med.strength,
                formulation_text=med.formulation,
                dosage_text=med.dosage_text,
                frequency_text=med.frequency_text,
                duration_text=med.duration_text,
                uncertainty_status=(
                    UncertaintyStatus.UNCERTAIN.value
                    if (uncertain or med.requires_review)
                    else UncertaintyStatus.CLEAR.value
                ),
                uncertain_fields=uncertain,
                user_confirmed=False,
                included=True,
            )
        )

    db.add(prescription)
    db.flush()
    audit_service.record(
        db,
        actor_id=user.id,
        action="prescription.analysed",
        target_type="prescription",
        target_id=prescription.id,
        meta={
            "engine": engine_name,
            "ai": structuring.source,
            "items": len(prescription.items),
            "document_type": document_type.value,
        },
    )
    db.commit()
    prescription = get_prescription(db, prescription.id, user)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return AnalyseResponse(
        prescription=to_out(prescription),
        extracted_text=ocr_text,
        preview_images=previews,
        processing=ProcessingInfo(
            ocr_engine=engine_name,
            ocr_available=engine is not None,
            handwriting_engine_used=handwriting_used,
            ai_source=structuring.source,
            elapsed_ms=elapsed_ms,
            preprocessing_steps=steps,
            notes=notes,
        ),
    )


def _item_out(item: PrescriptionItem, prescription: Prescription) -> PrescriptionItemOut:
    out = PrescriptionItemOut.model_validate(item)
    blocked = None
    medicine = item.matched_medicine
    if not item.included:
        blocked = "Excluded from this prescription"
    elif medicine is None:
        blocked = "Choose a matching medicine from the catalogue first"
    elif prescription.user_confirmation_status != UserConfirmationStatus.CONFIRMED.value:
        blocked = "Confirm the prescription details first"
    elif medicine.prescription_required:
        status = prescription.pharmacist_verification_status
        if status == VerificationStatus.REJECTED.value:
            blocked = "Rejected by the pharmacist"
        elif status == VerificationStatus.CLARIFICATION_REQUESTED.value:
            blocked = "The pharmacist asked for clarification"
        elif status != VerificationStatus.APPROVED.value and get_settings().require_pharmacist_approval:
            blocked = "Awaiting pharmacist verification"
    if (
        blocked is None
        and medicine is not None
        and not any(p.is_active and p.available_quantity > 0 for p in medicine.products)
    ):
        blocked = "Currently out of stock"
    out.can_add_to_cart = blocked is None
    out.blocked_reason = blocked
    return out


def to_out(prescription: Prescription) -> PrescriptionOut:
    out = PrescriptionOut.model_validate(prescription)
    out.items = [_item_out(item, prescription) for item in prescription.items]
    out.verifications = [
        VerificationOut(
            id=v.id,
            verification_status=v.verification_status,
            notes=v.notes,
            verified_at=v.verified_at,
            pharmacist_name=v.pharmacist.full_name if v.pharmacist else None,
        )
        for v in prescription.verifications
    ]
    out.ocr_confidence = (
        float(prescription.ocr_confidence) if prescription.ocr_confidence is not None else None
    )
    out.show_handwriting_disclaimer = prescription.document_type != DocumentType.PRINTED.value
    out.handwriting_disclaimer = HANDWRITING_DISCLAIMER if out.show_handwriting_disclaimer else None
    out.original_image_retained = False

    warnings: list[str] = []
    if prescription.ai_review_status in {AIReviewStatus.FALLBACK.value, AIReviewStatus.UNAVAILABLE.value}:
        warnings.append("Fields were read with simple rules. Check every value against the paper copy.")
    if out.ocr_confidence is not None and out.ocr_confidence < 0.75:
        warnings.append("Text recognition confidence is low. Check every field against your prescription.")
    unmatched = [i for i in out.items if i.included and i.match_status in {"none", "uncertain"}]
    if unmatched:
        warnings.append(f"{len(unmatched)} medicine(s) could not be matched confidently to the catalogue.")
    if not out.items:
        warnings.append("No medicines were recognised. Add them manually or upload a clearer image.")
    out.warnings = warnings
    return out


def _requires_pharmacist(prescription: Prescription) -> bool:
    return any(
        item.included and item.matched_medicine is not None and item.matched_medicine.prescription_required
        for item in prescription.items
    )


def confirm(db: Session, user: User, data: ConfirmRequest) -> ConfirmResponse:
    prescription = get_prescription(db, data.prescription_id, user)
    if prescription.processing_status != ProcessingStatus.COMPLETED.value:
        raise ConflictError("This prescription has not finished processing", code="not_ready")
    if prescription.pharmacist_verification_status == VerificationStatus.APPROVED.value:
        raise ConflictError(
            "This prescription has already been verified. Upload a new one to make changes.",
            code="already_verified",
        )

    items_by_id = {item.id: item for item in prescription.items}

    def resolve_medicine(medicine_id: int | None, name: str) -> tuple[int | None, MatchStatus, list]:
        if medicine_id is not None:
            chosen = db.get(Medicine, medicine_id)
            if chosen is None or not chosen.is_active:
                raise ValidationError("Selected medicine is not available", code="invalid_medicine")
            return medicine_id, MatchStatus.EXACT, None
        outcome = match_in_db(db, name)
        return (
            None,
            outcome.status if outcome.status != MatchStatus.EXACT else MatchStatus.POSSIBLE,
            outcome.candidates,
        )

    for incoming in data.items:
        item = items_by_id.get(incoming.item_id)
        if item is None:
            raise NotFoundError(f"Prescription item {incoming.item_id} not found")
        edited = (
            incoming.extracted_name != item.extracted_name
            or incoming.strength_text != item.strength_text
            or incoming.dosage_text != item.dosage_text
            or incoming.frequency_text != item.frequency_text
            or incoming.duration_text != item.duration_text
            or incoming.formulation_text != item.formulation_text
        )
        item.extracted_name = incoming.extracted_name
        item.strength_text = incoming.strength_text
        item.formulation_text = incoming.formulation_text
        item.dosage_text = incoming.dosage_text
        item.frequency_text = incoming.frequency_text
        item.duration_text = incoming.duration_text
        item.included = incoming.included
        if incoming.matched_medicine_id != item.matched_medicine_id or edited:
            medicine_id, status, candidates = resolve_medicine(
                incoming.matched_medicine_id, incoming.extracted_name
            )
            item.matched_medicine_id = medicine_id
            item.match_status = status.value
            if candidates is not None:
                item.candidates = candidates
        item.user_edited = item.user_edited or edited
        item.user_confirmed = incoming.included

    if len(prescription.items) + len(data.new_items) > MAX_ITEMS:
        raise ValidationError(f"A prescription can hold at most {MAX_ITEMS} medicines")
    for new in data.new_items:
        medicine_id, status, candidates = resolve_medicine(new.matched_medicine_id, new.extracted_name)
        prescription.items.append(
            PrescriptionItem(
                extracted_name=new.extracted_name,
                original_text=None,
                matched_medicine_id=medicine_id,
                match_status=status.value,
                candidates=candidates or [],
                strength_text=new.strength_text,
                formulation_text=new.formulation_text,
                dosage_text=new.dosage_text,
                frequency_text=new.frequency_text,
                duration_text=new.duration_text,
                uncertainty_status=UncertaintyStatus.CLEAR.value,
                uncertain_fields=[],
                user_confirmed=True,
                user_edited=True,
                included=True,
            )
        )

    prescription.customer_notes = data.customer_notes
    prescription.user_confirmation_status = UserConfirmationStatus.CONFIRMED.value
    db.flush()
    db.refresh(prescription)

    review_open = prescription.pharmacist_verification_status in (
        VerificationStatus.PENDING.value,
        VerificationStatus.CLARIFICATION_REQUESTED.value,
    )
    mandatory = get_settings().require_pharmacist_approval and _requires_pharmacist(prescription)
    if data.request_pharmacist_review or mandatory or review_open:
        prescription.pharmacist_verification_status = VerificationStatus.PENDING.value
    else:
        prescription.pharmacist_verification_status = VerificationStatus.NOT_REQUIRED.value

    audit_service.record(
        db,
        actor_id=user.id,
        action="prescription.confirmed",
        target_type="prescription",
        target_id=prescription.id,
        meta={"verification": prescription.pharmacist_verification_status},
    )
    db.commit()
    prescription = get_prescription(db, prescription.id, user)
    added: list[dict] = []
    skipped: list[dict] = []
    if data.add_to_cart:
        added, skipped = _add_confirmed_items_to_cart(db, user, prescription)
        prescription = get_prescription(db, prescription.id, user)
    return ConfirmResponse(**to_out(prescription).model_dump(), cart_added=added, cart_skipped=skipped)


def _add_confirmed_items_to_cart(
    db: Session, user: User, prescription: Prescription
) -> tuple[list[dict], list[dict]]:
    """Put one pack of every confirmed, matched, available medicine into the cart."""
    added: list[dict] = []
    skipped: list[dict] = []
    in_cart = {item.product_id for item in cart_service.get_cart(db, user).items}
    for item in prescription.items:
        if not item.included:
            continue
        medicine = item.matched_medicine
        name = medicine.medicine_name if medicine else item.extracted_name
        availability = _item_out(item, prescription)
        if not availability.can_add_to_cart:
            skipped.append({"name": name, "reason": availability.blocked_reason or "Not available"})
            continue
        if any(p.id in in_cart for p in medicine.products):
            skipped.append({"name": name, "reason": "Already in your cart"})
            continue
        stocked = sorted(
            (p for p in medicine.products if p.is_active and p.available_quantity > 0),
            key=lambda p: p.price,
        )
        try:
            cart_service.add_item(db, user, stocked[0].id, 1)
        except AppError as exc:
            skipped.append({"name": name, "reason": exc.message})
            continue
        in_cart.add(stocked[0].id)
        added.append(
            {
                "medicine_name": name,
                "product_id": stocked[0].id,
                "pack_size": stocked[0].pack_size,
                "quantity": 1,
            }
        )
    return added, skipped


def request_review(db: Session, user: User, prescription_id: int, data: ReviewRequest) -> PrescriptionOut:
    prescription = get_prescription(db, prescription_id, user)
    if prescription.user_confirmation_status != UserConfirmationStatus.CONFIRMED.value:
        raise ConflictError("Confirm the prescription before requesting a review", code="unconfirmed")
    if prescription.pharmacist_verification_status == VerificationStatus.APPROVED.value:
        raise ConflictError("This prescription is already verified", code="already_verified")
    prescription.pharmacist_verification_status = VerificationStatus.PENDING.value
    if data.message:
        note = f"Customer: {data.message.strip()}"
        prescription.customer_notes = (
            f"{prescription.customer_notes}\n{note}" if prescription.customer_notes else note
        )
    audit_service.record(
        db,
        actor_id=user.id,
        action="prescription.review_requested",
        target_type="prescription",
        target_id=prescription.id,
    )
    db.commit()
    return to_out(get_prescription(db, prescription.id, user))
