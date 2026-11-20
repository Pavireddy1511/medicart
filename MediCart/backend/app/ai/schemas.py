from pydantic import BaseModel, Field, field_validator

TEXT_FIELDS = (
    "original_text",
    "strength",
    "formulation",
    "dosage_text",
    "frequency_text",
    "duration_text",
    "composition",
)


class ExtractedMedicine(BaseModel):
    extracted_name: str = Field(min_length=1, max_length=200)
    original_text: str | None = Field(default=None, max_length=500)
    strength: str | None = Field(default=None, max_length=100)
    formulation: str | None = Field(default=None, max_length=100)
    dosage_text: str | None = Field(default=None, max_length=200)
    frequency_text: str | None = Field(default=None, max_length=200)
    duration_text: str | None = Field(default=None, max_length=200)
    composition: str | None = Field(default=None, max_length=300)
    uncertain_fields: list[str] = Field(default_factory=list)
    requires_review: bool = True

    @field_validator(*TEXT_FIELDS, mode="before")
    @classmethod
    def _blank_to_none(cls, value):
        if value is None:
            return None
        if isinstance(value, int | float):
            return str(value)
        text = str(value).strip()
        if not text or text.lower() in {"null", "none", "n/a", "na", "unknown", "-"}:
            return None
        return text

    @field_validator("extracted_name", mode="before")
    @classmethod
    def _clean_name(cls, value):
        return " ".join(str(value or "").split())

    @field_validator("uncertain_fields", mode="before")
    @classmethod
    def _coerce_fields(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(v) for v in value]


class StructuredPrescription(BaseModel):
    medicines: list[ExtractedMedicine] = Field(default_factory=list)
    overall_review_required: bool = True
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("medicines", mode="before")
    @classmethod
    def _drop_empty(cls, value):
        if not isinstance(value, list):
            return []
        kept = []
        for item in value:
            if isinstance(item, ExtractedMedicine):
                kept.append(item)
            elif isinstance(item, dict) and str(item.get("extracted_name", "")).strip():
                kept.append(item)
        return kept
