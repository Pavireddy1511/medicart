"""Catalogue matching for extracted medicine names.

Candidates are fetched from the database first and then scored with rapidfuzz, so the cost does
not grow with the size of the catalogue. On PostgreSQL two trigram-indexed queries are used:
name/brand similarity, and products whose salts contain the query ordered by popularity (products
per manufacturer, a proxy for how widely a brand is distributed). Elsewhere a LIKE prefilter
stands in.

Outcomes:
- exact:     one catalogue item carries that name, brand or single salt (pre-selected)
- possible:  a strong match, or several items share the generic (customer must pick)
- uncertain: a weak fuzzy match worth showing
- none:      nothing resembles the text
"""

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from app.models.catalogue import Medicine
from app.models.enums import MatchStatus
from app.utils.text import extract_strength, normalise_name

POSSIBLE_THRESHOLD = 90
UNCERTAIN_THRESHOLD = 72
SUGGESTION_THRESHOLD = 62
MAX_CANDIDATES = 6
FETCH_LIMIT = 60

_RANK = {MatchStatus.NONE: 0, MatchStatus.UNCERTAIN: 1, MatchStatus.POSSIBLE: 2, MatchStatus.EXACT: 3}
_FIELD_RANK = {"medicine_name": 0, "brand_name": 1, "generic_name": 2}


@dataclass
class CatalogueEntry:
    id: int
    medicine_name: str
    brand_name: str | None
    generic_name: str | None
    strength: str | None
    formulation: str | None
    prescription_required: bool
    search_name: str | None = None
    composition_key: str | None = None
    manufacturer: str | None = None
    popularity: int = 0
    norm: dict[str, str] = field(default_factory=dict)
    salts: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.norm = {
            "medicine_name": self.search_name or normalise_name(self.medicine_name),
            "brand_name": normalise_name(self.brand_name or ""),
        }
        if self.composition_key:
            self.salts = [s for s in self.composition_key.split("|") if s]
        elif self.generic_name:
            self.salts = [normalise_name(p) for p in self.generic_name.split("+") if p.strip()]
        self.salts = [s for s in self.salts if s]


@dataclass
class MatchOutcome:
    status: MatchStatus
    medicine_id: int | None
    candidates: list[dict]


ENTRY_COLUMNS = (
    Medicine.id,
    Medicine.medicine_name,
    Medicine.brand_name,
    Medicine.generic_name,
    Medicine.strength,
    Medicine.formulation,
    Medicine.prescription_required,
    Medicine.search_name,
    Medicine.composition_key,
    Medicine.manufacturer,
    Medicine.popularity,
)


def _entries(rows) -> list[CatalogueEntry]:
    return [CatalogueEntry(*row) for row in rows]


def load_catalogue(db: Session) -> list[CatalogueEntry]:
    """Every active medicine. Fine for tests and small catalogues; use fetch_candidates otherwise."""
    rows = db.execute(select(*ENTRY_COLUMNS).where(Medicine.is_active.is_(True))).all()
    return _entries(rows)


def fetch_candidates(db: Session, extracted_name: str, limit: int = FETCH_LIMIT) -> list[CatalogueEntry]:
    """Pull a short list of plausible rows for one name from the database."""
    query = normalise_name(extracted_name)
    if not query:
        return []
    bind = db.get_bind()
    active = Medicine.is_active.is_(True)

    if bind is not None and bind.dialect.name == "postgresql":
        db.execute(text("SELECT set_config('pg_trgm.similarity_threshold', '0.28', true)"))
        similarity = func.greatest(
            func.similarity(Medicine.search_name, query),
            func.similarity(func.coalesce(Medicine.brand_name, ""), query),
        )
        by_name = (
            select(*ENTRY_COLUMNS)
            .where(
                active,
                or_(
                    Medicine.search_name.op("%")(query),
                    Medicine.brand_name.op("%")(query),
                    Medicine.search_name.like(f"{query}%"),
                ),
            )
            .order_by(
                similarity.desc(),
                Medicine.search_name.like(f"%{query}%").desc(),
                Medicine.popularity.desc(),
                func.length(Medicine.medicine_name),
            )
            .limit(limit)
        )
        by_salt = (
            select(*ENTRY_COLUMNS)
            .where(
                active,
                or_(
                    Medicine.composition_key.op("%")(query),
                    # whole-ingredient hits for short names such as "ors" that trigram similarity misses
                    Medicine.composition_key == query,
                    Medicine.composition_key.like(f"{query}|%"),
                    Medicine.composition_key.like(f"%|{query}"),
                    Medicine.composition_key.like(f"%|{query}|%"),
                ),
            )
            .order_by(Medicine.popularity.desc(), func.length(Medicine.medicine_name))
            .limit(limit)
        )
        seen: set[int] = set()
        merged: list[CatalogueEntry] = []
        for stmt in (by_name, by_salt):
            for entry in _entries(db.execute(stmt).all()):
                if entry.id not in seen:
                    seen.add(entry.id)
                    merged.append(entry)
        return merged

    probe = f"%{query[:4]}%"
    stmt = (
        select(*ENTRY_COLUMNS)
        .where(
            active,
            or_(
                Medicine.search_name.like(probe),
                func.lower(Medicine.medicine_name).like(probe),
                Medicine.composition_key.like(probe),
                func.lower(Medicine.brand_name).like(probe),
                func.lower(Medicine.generic_name).like(probe),
            ),
        )
        .limit(max(limit * 10, 500))
    )
    return _entries(db.execute(stmt).all())


def _numbers(value: str | None) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", value or ""))


def _strength_adjustment(hint: str | None, entry: CatalogueEntry) -> int:
    if not hint:
        return 0
    hint_numbers = _numbers(hint)
    entry_numbers = _numbers(entry.strength) | _numbers(entry.medicine_name)
    if not hint_numbers or not entry_numbers:
        return 0
    return 4 if hint_numbers & entry_numbers else -12


def _form_adjustment(hint: str | None, entry_form: str | None) -> int:
    if not hint or not entry_form:
        return 0
    return 3 if hint.lower() == entry_form.lower() else -6


def _extra_salts(query: str, entry: CatalogueEntry) -> int:
    """Ingredients the product has beyond those named in the query (0 when the query names none).

    "Pantoprazole" should prefer plain pantoprazole over a Domperidone + Pantoprazole combination,
    while a brand query such as "Pan D" is left alone.
    """
    mentioned = _mentioned_salts(query, entry)
    return len(entry.salts) - mentioned if mentioned else 0


def _mentioned_salts(query: str, entry: CatalogueEntry) -> int:
    return sum(1 for salt in entry.salts if salt and salt in query)


def _candidate(entry: CatalogueEntry, score: float, matched_on: str) -> dict:
    return {
        "medicine_id": entry.id,
        "medicine_name": entry.medicine_name,
        "brand_name": entry.brand_name,
        "generic_name": entry.generic_name,
        "strength": entry.strength,
        "formulation": entry.formulation,
        "prescription_required": entry.prescription_required,
        "score": round(float(score), 1),
        "matched_on": matched_on,
    }


def _score_entry(query: str, entry: CatalogueEntry) -> tuple[float, bool, str]:
    """Best (score, is_exact, field) over the entry's name, brand and individual salts."""
    best_score, best_field, exact = 0.0, "medicine_name", False
    fields = list(entry.norm.items()) + [("generic_name", salt) for salt in entry.salts]
    for field_name, value in fields:
        if not value:
            continue
        if value == query:
            score, is_exact = 100.0, True
        else:
            shorter, longer = min(len(query), len(value)), max(len(query), len(value))
            comparable = shorter >= 5 and shorter / longer >= 0.6
            score = max(
                fuzz.ratio(query, value),
                fuzz.token_set_ratio(query, value) - 3,
                fuzz.partial_ratio(query, value) - 8 if comparable else 0,
            )
            is_exact = False
        if (is_exact and not exact) or (is_exact == exact and score > best_score):
            best_score, best_field, exact = score, field_name, is_exact
    return best_score, exact, best_field


def match_name(
    extracted_name: str,
    catalogue: list[CatalogueEntry],
    strength_hint: str | None = None,
    form_hint: str | None = None,
) -> MatchOutcome:
    query = normalise_name(extracted_name)
    if not query:
        return MatchOutcome(MatchStatus.NONE, None, [])

    scored: list[tuple[float, bool, str, CatalogueEntry]] = []
    for entry in catalogue:
        score, exact, field_name = _score_entry(query, entry)
        adjusted = min(
            100.0,
            score
            + _strength_adjustment(strength_hint, entry)
            + _form_adjustment(form_hint, entry.formulation),
        )
        if not exact and _extra_salts(query, entry):
            adjusted -= 6
        if adjusted >= SUGGESTION_THRESHOLD or exact:
            scored.append((adjusted, exact, field_name, entry))

    if not scored:
        return MatchOutcome(MatchStatus.NONE, None, [])

    # exact first, then score, direct name hits, no unrequested ingredients, names containing the
    # query, popularity, simplicity
    scored.sort(
        key=lambda item: (
            not item[1],
            -round(item[0]),
            _FIELD_RANK.get(item[2], 3),
            _extra_salts(query, item[3]),
            -_mentioned_salts(query, item[3]),
            0 if query in (item[3].norm.get("medicine_name") or "") else 1,
            -item[3].popularity,
            len(item[3].salts),
            len(item[3].medicine_name),
        )
    )
    candidates = [
        _candidate(entry, score, field_name) for score, _, field_name, entry in scored[:MAX_CANDIDATES]
    ]

    exact_entries = [(entry, field_name) for score, exact, field_name, entry in scored if exact]
    if exact_entries:
        if len(exact_entries) == 1:
            return MatchOutcome(MatchStatus.EXACT, exact_entries[0][0].id, candidates)
        hint_numbers = _numbers(strength_hint)
        narrowed = [
            (e, f)
            for e, f in exact_entries
            if hint_numbers and hint_numbers & (_numbers(e.strength) | _numbers(e.medicine_name))
        ]
        if len(narrowed) == 1:
            return MatchOutcome(MatchStatus.EXACT, narrowed[0][0].id, candidates)
        if len(narrowed) > 1 and form_hint:
            by_form = [(e, f) for e, f in narrowed if (e.formulation or "").lower() == form_hint.lower()]
            if len(by_form) == 1:
                return MatchOutcome(MatchStatus.EXACT, by_form[0][0].id, candidates)
        # Several products share this name or generic. If exactly one carries it as its own
        # name (e.g. "Paracetamol" -> "Paracetamol 500"), that one wins; brands stay as candidates.
        pool = narrowed or exact_entries
        by_name = [e for e, f in pool if f == "medicine_name"]
        if len(by_name) == 1:
            return MatchOutcome(MatchStatus.EXACT, by_name[0].id, candidates)
        return MatchOutcome(MatchStatus.POSSIBLE, None, candidates)

    top_score = scored[0][0]
    if top_score >= POSSIBLE_THRESHOLD:
        return MatchOutcome(MatchStatus.POSSIBLE, None, candidates)
    if top_score >= UNCERTAIN_THRESHOLD:
        return MatchOutcome(MatchStatus.UNCERTAIN, None, candidates)
    return MatchOutcome(MatchStatus.NONE, None, candidates)


def composition_names(composition: str) -> list[str]:
    from app.ai.structuring import composition_names as _names

    return _names(composition)


def match_with_composition(
    extracted_name: str,
    composition: str | None,
    catalogue: list[CatalogueEntry],
    strength_hint: str | None = None,
    *,
    form_hint: str | None = None,
    extra_catalogue: dict[str, list[CatalogueEntry]] | None = None,
) -> MatchOutcome:
    """Match the brand line first; if that fails, try the generic ingredients written under it.

    A hit through the composition is never auto-selected: the brand on the prescription may not
    be the product in the catalogue, so the customer and pharmacist have to pick it explicitly.
    """
    outcome = match_name(extracted_name, catalogue, strength_hint, form_hint)
    if not composition or outcome.status in {MatchStatus.EXACT, MatchStatus.POSSIBLE}:
        return outcome

    merged = list(outcome.candidates)
    seen = {c["medicine_id"] for c in merged}
    best_status = outcome.status
    for generic in composition_names(composition):
        pool = (extra_catalogue or {}).get(generic, catalogue)
        alt = match_name(generic, pool, extract_strength(generic) or strength_hint, form_hint)
        for candidate in alt.candidates:
            if candidate["medicine_id"] in seen:
                continue
            seen.add(candidate["medicine_id"])
            merged.append({**candidate, "matched_on": f"composition {candidate['matched_on']}"})
        alt_status = MatchStatus.POSSIBLE if alt.status == MatchStatus.EXACT else alt.status
        if _RANK[alt_status] > _RANK[best_status]:
            best_status = alt_status
    merged.sort(key=lambda c: c["score"], reverse=True)
    return MatchOutcome(best_status, None, merged[:MAX_CANDIDATES])


def match_in_db(
    db: Session,
    extracted_name: str,
    composition: str | None = None,
    strength_hint: str | None = None,
    form_hint: str | None = None,
) -> MatchOutcome:
    """Database-backed matching used by the prescription pipeline."""
    pool = fetch_candidates(db, extracted_name)
    extra = {}
    if composition:
        for generic in composition_names(composition):
            extra[generic] = fetch_candidates(db, generic)
    return match_with_composition(
        extracted_name, composition, pool, strength_hint, form_hint=form_hint, extra_catalogue=extra or None
    )
