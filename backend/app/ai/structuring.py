import logging
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.ai.groq_client import GroqUnavailable, structure_with_groq
from app.ai.schemas import ExtractedMedicine, StructuredPrescription
from app.core.config import Settings
from app.utils.text import (
    DOSING_WORDS,
    FORMULATION_WORDS,
    STRENGTH_RE,
    clean_ocr_line,
    extract_dosage,
    extract_duration,
    extract_formulation,
    extract_frequency,
    extract_strength,
    normalise_name,
)

logger = logging.getLogger(__name__)

HEADER_WORDS = re.compile(
    r"\b(dr\.?|doctor|hospital|clinic|patient|age|sex|gender|date|dob|phone|mobile|mob|address|"
    r"reg\.?\s*no|regd|signature|diagnosis|complaints?|findings?|review|bp|pulse|weight|height|"
    r"temp|name\s*:|m\.?b\.?b\.?s|m\.?d\.?|m\.?s\.?|consultant|physician|prescription|rx\s*$|"
    r"malaria|fever|chills|infection|diabetes|hypertension|asthma|allergy|allergic|"
    r"investigations?|tests?|reports?|symptoms?|history|timing|closed|id\s*:|uhid|opd|ipd|"
    r"follow\s*up|advice|medicine\s+name|dosage|duration|generics?|bpm|spo2|rbs|fbs|"
    r"nagara?|road|street|lane|layout|colony|institute|university|research|centre|center|"
    r"medical\s+sciences|taluk|dist|pin\s*code|email|www|c/o)\b",
    re.IGNORECASE,
)
STOP_WORDS = re.compile(r"\b(advice|follow\s*up|signature|instructions?|substitute)\b", re.IGNORECASE)
# Clinical notes (complaints, impression, diagnosis, lab values) are never medicines, even with numbers.
CLINICAL_NOTE = re.compile(
    r"^\s*(?:c\s*/\s*o\b|complains?\b|imp(?:ression)?\b\s*[:.-]?|dx\b|diag(?:nosis)?\b|"
    r"provisional\b|k/c/o\b|h/o\b|o/e\b)|\b(?:rbs|fbs|ppbs|hba1c|spo2|bpm|mmhg|mg\s*%|mg/dl)\b",
    re.IGNORECASE,
)
LEADING_MARKER = re.compile(r"^\s*(?:rx|r/|\d{1,2}[.)]|[-*•·]|[ivx]+[.)])\s*", re.IGNORECASE)
NUMBERED_MARKER = re.compile(r"^\s*\d{1,2}[.)]\s*")
DIGITS_ONLY = re.compile(r"^[\d\s/.:,()-]+$")
PAREN_NOTE = re.compile(r"^\s*\(")
NAME_TOKEN = re.compile(r"^[A-Za-z][A-Za-z'-]{2,}$")
LONG_NUMBER = re.compile(r"\d{5,}")


@dataclass
class StructuringOutcome:
    result: StructuredPrescription
    source: str  # groq | fallback | unavailable | skipped
    model: str | None = None
    reason: str | None = None
    messages: list[str] = field(default_factory=list)


def _tokens(line: str) -> list[str]:
    return LEADING_MARKER.sub("", line.strip()).split()


def _is_composition_line(line: str) -> bool:
    """'DOXYLAMINE 10 mg + PYRIDOXINE 10 mg' style lines that describe the previous item."""
    text = line.strip()
    if NUMBERED_MARKER.match(text) or PAREN_NOTE.match(text):
        return False
    if HEADER_WORDS.search(text):
        return False
    return bool(STRENGTH_RE.search(text)) and not any(
        t.lower().strip(".:") in FORMULATION_WORDS for t in text.split()[:1]
    )


def _looks_like_medicine(line: str, lenient: bool) -> bool:
    text = line.strip()
    if len(text) < 3 or DIGITS_ONLY.match(text) or PAREN_NOTE.match(text):
        return False
    if CLINICAL_NOTE.search(text):
        return False
    has_strength = bool(STRENGTH_RE.search(text))
    if HEADER_WORDS.search(text) and not has_strength:
        return False
    if LONG_NUMBER.search(text) and not has_strength:
        return False
    tokens = _tokens(text)
    if not tokens:
        return False
    first = tokens[0].lower().strip(".:")
    if first in FORMULATION_WORDS or has_strength:
        return True
    if NUMBERED_MARKER.match(text) and len(tokens) <= 8:
        return True
    if lenient:
        return any(NAME_TOKEN.match(t) for t in tokens) and len(tokens) <= 6
    return False


def _split_name(line: str) -> tuple[str, str | None]:
    """Return (name, bare_strength). The name stops at the first dosing word or number."""
    tokens = _tokens(line)
    while tokens and tokens[0].lower().strip(".:") in FORMULATION_WORDS:
        tokens.pop(0)
    name: list[str] = []
    bare_strength = None
    for token in tokens:
        bare = token.strip(".,;:()")
        lowered = bare.lower()
        if not bare:
            continue
        if lowered in DOSING_WORDS and name:
            break
        if STRENGTH_RE.match(bare):
            break
        if bare[0].isdigit():
            # "1 Morning" is a dose count; "500", "2.5" or "10/SR" is a strength.
            if name and bare_strength is None and not DIGITS_ONLY.match(bare):
                bare_strength = bare
            elif name and bare_strength is None and re.fullmatch(r"\d+(?:[./]\d+)?", bare):
                number = float(bare.split("/")[0])
                if 5 <= number <= 5000 or "." in bare or "/" in bare:
                    bare_strength = bare
            break
        if lowered in {"+", "&", "-", "–"}:
            break
        name.append(bare)
    return " ".join(name).strip(" -:;.,"), bare_strength


def composition_names(line: str) -> list[str]:
    parts = re.split(r"\s*(?:\+|&|,|/)\s*", line)
    names = []
    for part in parts:
        name, _ = _split_name(part)
        if name and NAME_TOKEN.match(name.split()[0]):
            names.append(name)
    return names


def heuristic_structure(lines: list[str], lenient: bool = False) -> StructuredPrescription:
    medicines: list[ExtractedMedicine] = []
    stopped = False
    for index, raw in enumerate(lines):
        if STOP_WORDS.search(raw) and not STRENGTH_RE.search(raw):
            stopped = True
        if stopped:
            break
        if not _looks_like_medicine(raw, lenient):
            continue
        if medicines and _is_composition_line(raw):
            previous_line = lines[index - 1] if index else ""
            continues_item = NUMBERED_MARKER.match(previous_line) or PAREN_NOTE.match(previous_line)
            continues_composition = medicines[-1].composition is not None and _is_composition_line(
                previous_line
            )
            if continues_item or continues_composition:
                joined = f"{medicines[-1].composition or ''} + {raw.strip()}".strip(" +")
                medicines[-1].composition = joined[:300]
                if medicines[-1].strength is None:
                    medicines[-1].strength = extract_strength(raw)
                continue
        name, bare_strength = _split_name(raw)
        if len(name) < 3 or not re.search(r"[A-Za-z]{3,}", name):
            continue
        strength = extract_strength(raw) or bare_strength
        frequency = extract_frequency(raw)
        duration = extract_duration(raw)
        dosage = extract_dosage(raw)
        uncertain = [
            label
            for label, value in (
                ("strength", strength),
                ("frequency_text", frequency),
                ("duration_text", duration),
            )
            if value is None
        ]
        medicines.append(
            ExtractedMedicine(
                extracted_name=name,
                original_text=raw.strip()[:500],
                strength=strength,
                formulation=extract_formulation(raw),
                dosage_text=dosage,
                frequency_text=frequency,
                duration_text=duration,
                uncertain_fields=uncertain,
                requires_review=True,
            )
        )
    return StructuredPrescription(
        medicines=medicines,
        overall_review_required=True,
        notes="Rule-based extraction; every field needs manual review.",
    )


def _best_line(text: str, lines: list[str]) -> tuple[str | None, float]:
    best, best_score = None, 0.0
    for line in lines:
        score = fuzz.partial_ratio(text.lower(), line.lower())
        if score > best_score:
            best, best_score = line, score
    return best, best_score


def guard_against_invention(result: StructuredPrescription, lines: list[str]) -> StructuredPrescription:
    """Anything the model reports must be traceable to the OCR text, or it is flagged."""
    joined = "\n".join(lines).lower()
    kept: list[ExtractedMedicine] = []
    for med in result.medicines:
        name_norm = normalise_name(med.extracted_name)
        line, score = _best_line(med.extracted_name, lines)
        if not med.original_text and line:
            med.original_text = line.strip()[:500]
        # a "medicine" taken from a complaint, impression or lab-value line is dropped outright
        if CLINICAL_NOTE.search(med.original_text or line or ""):
            continue
        kept.append(med)
        # dose details the model left blank but that are written on the line
        source = clean_ocr_line(med.original_text or line or "")
        if source:
            med.frequency_text = med.frequency_text or extract_frequency(source)
            med.duration_text = med.duration_text or extract_duration(source)
            med.dosage_text = med.dosage_text or extract_dosage(source)
            med.strength = med.strength or extract_strength(source)
        if score < 80 and (not name_norm or fuzz.partial_ratio(name_norm, joined) < 80):
            if "extracted_name" not in med.uncertain_fields:
                med.uncertain_fields.append("extracted_name")
            med.requires_review = True
        if med.strength:
            numbers = re.findall(r"\d+(?:\.\d+)?", med.strength)
            if numbers and not all(re.search(rf"(?<![\d.]){re.escape(n)}(?![\d.])", joined) for n in numbers):
                med.strength = None
                if "strength" not in med.uncertain_fields:
                    med.uncertain_fields.append("strength")
                med.requires_review = True
        if med.uncertain_fields:
            med.requires_review = True
    result.medicines = kept
    if any(m.requires_review for m in result.medicines) or not result.medicines:
        result.overall_review_required = True
    return result


def structure_prescription(
    ocr_text: str, lines: list[str], settings: Settings, *, handwritten: bool = False
) -> StructuringOutcome:
    lines = [clean_ocr_line(line) for line in lines if line.strip()]
    ocr_text = "\n".join(lines)
    if not ocr_text.strip():
        return StructuringOutcome(
            result=StructuredPrescription(medicines=[], overall_review_required=True),
            source="skipped",
            messages=["No text was recognised, so there is nothing to structure."],
        )

    if settings.groq_configured:
        try:
            parsed, model = structure_with_groq(ocr_text, settings)
            return StructuringOutcome(
                result=guard_against_invention(parsed, lines), source="groq", model=model
            )
        except GroqUnavailable as exc:
            logger.warning("Groq unavailable (%s): %s", exc.reason, exc.message)
            fallback = guard_against_invention(heuristic_structure(lines, lenient=handwritten), lines)
            return StructuringOutcome(
                result=fallback,
                source="fallback",
                reason=exc.reason,
                messages=[f"AI structuring unavailable ({exc.message}). Rule-based parsing was used."],
            )

    fallback = guard_against_invention(heuristic_structure(lines, lenient=handwritten), lines)
    return StructuringOutcome(
        result=fallback,
        source="unavailable",
        reason="not_configured",
        messages=["Groq is not configured; rule-based parsing was used instead."],
    )
