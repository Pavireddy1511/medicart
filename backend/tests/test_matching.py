from app.ai.schemas import ExtractedMedicine, StructuredPrescription
from app.ai.structuring import guard_against_invention, heuristic_structure
from app.models.enums import MatchStatus
from app.services.matching_service import load_catalogue, match_name
from app.utils.text import extract_frequency, extract_strength, normalise_name


def test_normalise_name_strips_strength_and_form():
    assert normalise_name("Tab. Paracetamol 500mg") == "paracetamol"
    assert normalise_name("CAP AMOXICILLIN 500 MG") == "amoxicillin"
    assert normalise_name("Syp Kofend 100 ml") == "kofend"


def test_strength_and_frequency_extraction():
    assert extract_strength("Metformin 500 mg 1-0-1 x 30 days") == "500 mg"
    assert extract_frequency("Metformin 500 mg 1-0-1 x 30 days") == "1-0-1"
    assert extract_frequency("Tab Cetirizine 10mg OD at night") == "OD, night"


def test_exact_possible_uncertain_and_none(db, catalogue):
    entries = load_catalogue(db)

    exact = match_name("Paracetamol 500", entries)
    assert exact.status == MatchStatus.EXACT
    assert exact.medicine_id == catalogue["paracetamol"].id

    by_brand = match_name("Tab Allerfree 10mg", entries)
    assert by_brand.status == MatchStatus.EXACT
    assert by_brand.medicine_id == catalogue["cetirizine"].id

    typo = match_name("Amoxicilin", entries)
    assert typo.status == MatchStatus.POSSIBLE
    assert typo.medicine_id is None  # never auto-pick a fuzzy match
    assert typo.candidates[0]["medicine_id"] == catalogue["amoxicillin"].id

    vague = match_name("Metfrmn", entries)
    assert vague.status in {MatchStatus.UNCERTAIN, MatchStatus.NONE}
    assert vague.medicine_id is None

    nothing = match_name("Zyxwvutsrq", entries)
    assert nothing.status == MatchStatus.NONE
    assert nothing.candidates == []


def test_generic_name_shared_by_two_medicines_is_not_auto_selected(db, catalogue):
    from tests.conftest import make_medicine

    make_medicine(
        db,
        "Paracetamol 650",
        category=catalogue["general"],
        strength="650 mg",
        generic="Paracetamol",
        brand="Febrinil Forte",
        sku="SKU-PCM-650",
    )
    entries = load_catalogue(db)
    ambiguous = match_name("Paracetamol", entries)
    assert ambiguous.status == MatchStatus.POSSIBLE
    assert ambiguous.medicine_id is None
    assert len(ambiguous.candidates) >= 2

    narrowed = match_name("Paracetamol", entries, strength_hint="650 mg")
    assert narrowed.status == MatchStatus.EXACT
    assert narrowed.candidates[0]["strength"] == "650 mg"


def test_heuristic_structure_parses_typical_lines():
    lines = [
        "Dr. A. Sharma MBBS",
        "City Clinic, Hyderabad",
        "Patient: Demo Person   Age: 34",
        "Rx",
        "1. Tab Paracetamol 500mg 1-0-1 x 5 days",
        "2. Cap Amoxicillin 500 mg TDS for 7 days",
        "3. Syp Kofend 10ml BD",
        "Review after 1 week",
    ]
    result = heuristic_structure(lines)
    names = [m.extracted_name for m in result.medicines]
    assert names == ["Paracetamol", "Amoxicillin", "Kofend"]
    first = result.medicines[0]
    assert first.strength == "500mg"
    assert first.frequency_text == "1-0-1"
    assert first.duration_text and "5 days" in first.duration_text
    assert first.formulation == "tablet"
    assert all(m.requires_review for m in result.medicines)
    assert result.overall_review_required is True


def test_guard_flags_invented_names_and_strengths():
    lines = ["Tab Paracetamol 500mg 1-0-1"]
    invented = StructuredPrescription(
        medicines=[
            ExtractedMedicine(
                extracted_name="Paracetamol", strength="500 mg", uncertain_fields=[], requires_review=False
            ),
            ExtractedMedicine(
                extracted_name="Ibuprofen", strength="400 mg", uncertain_fields=[], requires_review=False
            ),
        ],
        overall_review_required=False,
    )
    guarded = guard_against_invention(invented, lines)
    good, bad = guarded.medicines
    assert good.requires_review is False and good.original_text == lines[0]
    assert "extracted_name" in bad.uncertain_fields
    assert bad.strength is None and "strength" in bad.uncertain_fields
    assert bad.requires_review is True
    assert guarded.overall_review_required is True


def test_clean_ocr_line_repairs_common_damage():
    from app.utils.text import clean_ocr_line

    assert clean_ocr_line("1)TAB.ABCIXIMAB 1Morning 8Days") == "1) TAB. ABCIXIMAB 1 Morning 8 Days"
    assert clean_ocr_line("CLARITHROMYCINIPSOOMG") == "CLARITHROMYCIN IP 500 mg"
    assert clean_ocr_line("FOLICACID 2.SMG") == "FOLICACID 2.5 mg"
    assert clean_ocr_line("3. Tab Cetirizine 10mg 0D at night") == "3. Tab Cetirizine 10 mg OD at night"


def test_heuristic_reads_printed_clinic_format_with_compositions():
    from app.ai.structuring import structure_prescription
    from app.core.config import get_settings

    lines = [
        "Diagnosis:",
        "·MALARIA",
        "Medicine Name Dosage Duration",
        "1)TAB.ABCIXIMAB 1Morning 8Days",
        "(Tot:8 Tab)",
        "2)TAB.VOMILAST 1Morning,1 Night 8Days",
        "(AfterFood) (Tot:16Tab)",
        "DOXYLAMINE10MG·PYRIDOXINE10MG",
        "FOLICACID 2.SMG",
        "3)CAP.ZOCLAR500 1Morning 3Days",
        "CLARITHROMYCINIPSOOMG",
        "Advice:",
        "·EATEASYTODIGESTFOOD LIKEBOILED RICEWITHDAAL",
    ]
    result = structure_prescription("\n".join(lines), lines, get_settings()).result
    names = [m.extracted_name for m in result.medicines]
    assert names == ["ABCIXIMAB", "VOMILAST", "ZOCLAR"]
    first, second, third = result.medicines
    assert first.strength is None and first.frequency_text == "1 Morning" and first.duration_text == "8 Days"
    assert "DOXYLAMINE" in (second.composition or "") and "FOLICACID 2.5 mg" in (second.composition or "")
    assert second.duration_text == "8 Days"
    assert third.strength == "500" and third.composition == "CLARITHROMYCIN IP 500 mg"


def test_match_with_composition_surfaces_generic_brands(db, catalogue):
    from app.services.matching_service import match_with_composition

    entries = load_catalogue(db)
    outcome = match_with_composition("Zyquin", "AMOXICILLIN 500 MG", entries, "500")
    assert outcome.status == MatchStatus.POSSIBLE
    assert outcome.medicine_id is None  # never auto-selected through a composition hit
    assert outcome.candidates[0]["medicine_id"] == catalogue["amoxicillin"].id
    assert outcome.candidates[0]["matched_on"].startswith("composition")

    direct = match_with_composition("Amoxicillin", "AMOXICILLIN 500 MG", entries, "500 mg")
    assert direct.status == MatchStatus.EXACT  # brand line matched on its own, composition unused


def test_letterhead_and_ids_are_not_medicines():
    from app.ai.structuring import heuristic_structure
    from app.utils.text import clean_ocr_line

    lines = [
        "Adichunchanagiri Institute of Medical Sciences",
        "Hospital & Research Centre",
        "BalagangadharanathaNagara571448",
        "Name. Vivek.S",
        "UHID/IPNo 26101",
        "PR-60bpm",
        "Tab Dolo 650 1-0-1",
    ]
    cleaned = [clean_ocr_line(line) for line in lines]
    result = heuristic_structure(cleaned, lenient=True)
    assert [m.extracted_name for m in result.medicines] == ["Dolo"]
    assert result.medicines[0].strength == "650"


def test_clinical_note_lines_are_not_medicines():
    from app.ai.structuring import heuristic_structure

    lines = [
        "Rx",
        "C/o giddiness, sleeplessness",
        "Imp: hypoglycemia (RBS - 30 mg%)",
        "Tab Dolo 650 1-0-1 x 3 days",
    ]
    result = heuristic_structure(lines, lenient=True)
    assert [m.extracted_name for m in result.medicines] == ["Dolo"]


def test_guard_drops_model_items_taken_from_clinical_notes():
    from app.ai.schemas import ExtractedMedicine, StructuredPrescription

    lines = ["C/o giddiness", "Imp: hypoglycemia (RBS - 30 mg%)", "Tab Dolo 650 1-0-1"]
    model_output = StructuredPrescription(
        medicines=[
            ExtractedMedicine(extracted_name="hypoglycemia", original_text=lines[1]),
            ExtractedMedicine(extracted_name="Dolo", strength="650"),
        ]
    )
    guarded = guard_against_invention(model_output, lines)
    assert [m.extracted_name for m in guarded.medicines] == ["Dolo"]
    assert guarded.medicines[0].frequency_text == "1-0-1"  # backfilled from the line


def test_single_ingredient_query_prefers_plain_product_over_combination(db, catalogue):
    from tests.conftest import make_medicine

    make_medicine(
        db,
        "Pantocid Tablet",
        category=catalogue["specialist"],
        strength="40 mg",
        generic="Pantoprazole",
        brand="Pantocid",
        sku="SKU-PANTOCID",
    )
    make_medicine(
        db,
        "Pan D Pantoprazole Combo Tablet",
        category=catalogue["specialist"],
        strength="40 mg / 10 mg",
        generic="Pantoprazole + Domperidone",
        brand="Pan D",
        sku="SKU-PAND",
    )
    outcome = match_name("Pantoprazole", load_catalogue(db), "40 mg", "tablet")
    names = [c["medicine_name"] for c in outcome.candidates]
    assert names.index("Pantocid Tablet") < names.index("Pan D Pantoprazole Combo Tablet")

    both = match_name("Pantoprazole Domperidone", load_catalogue(db))
    assert both.candidates[0]["medicine_name"] == "Pan D Pantoprazole Combo Tablet"
