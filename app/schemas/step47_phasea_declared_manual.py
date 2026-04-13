from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DECLARED_LOCATION_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")
DECLARED_MANUAL_DATA_STRENGTH = "declared_manual"
DECLARED_MANUAL_IS_LEGAL_TRUTH = False
DECLARED_MANUAL_IS_TEST_DATA = True


def normalize_declared_location(value: str) -> str:
    normalized = str(value or "").strip().upper()
    if not normalized:
        raise ValueError("declared_location is required")
    if not DECLARED_LOCATION_PATTERN.fullmatch(normalized):
        raise ValueError(
            "declared_location must use structured code format with only A-Z, 0-9, underscore, or hyphen"
        )
    return normalized


def normalize_required_text(value: str, *, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    return normalized


class Step47PhaseADeclaredManualCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    declared_by: str = Field(min_length=1)
    declared_location: str = Field(min_length=1)
    source_record_reference: str = Field(min_length=1)

    @model_validator(mode="after")
    def normalize_fields(self) -> "Step47PhaseADeclaredManualCreate":
        self.declared_by = normalize_required_text(self.declared_by, field_name="declared_by")
        self.declared_location = normalize_declared_location(self.declared_location)
        self.source_record_reference = normalize_required_text(
            self.source_record_reference,
            field_name="source_record_reference",
        )
        return self


class Step47PhaseADeclaredManualCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corrected_by: str = Field(min_length=1)
    correction_reason: str = Field(min_length=1)
    declared_location: str | None = None
    source_record_reference: str | None = None

    @model_validator(mode="after")
    def normalize_fields(self) -> "Step47PhaseADeclaredManualCorrection":
        self.corrected_by = normalize_required_text(self.corrected_by, field_name="corrected_by")
        self.correction_reason = normalize_required_text(
            self.correction_reason,
            field_name="correction_reason",
        )
        if self.declared_location is not None:
            self.declared_location = normalize_declared_location(self.declared_location)
        if self.source_record_reference is not None:
            self.source_record_reference = normalize_required_text(
                self.source_record_reference,
                field_name="source_record_reference",
            )
        if self.declared_location is None and self.source_record_reference is None:
            raise ValueError("at least one correction field is required")
        return self


class Step47PhaseADeclaredManualSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int
    data_strength: Literal["declared_manual"] = DECLARED_MANUAL_DATA_STRENGTH
    is_legal_truth: Literal[False] = DECLARED_MANUAL_IS_LEGAL_TRUTH
    is_test_data: Literal[True] = DECLARED_MANUAL_IS_TEST_DATA
    declared_by: str
    declared_at: datetime
    declared_location: str
    source_record_reference: str


class Step47PhaseADeclaredManualCorrectionTraceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)

    id: int
    declaration_id: int
    data_strength: Literal["declared_manual"] = DECLARED_MANUAL_DATA_STRENGTH
    is_legal_truth: Literal[False] = DECLARED_MANUAL_IS_LEGAL_TRUTH
    is_test_data: Literal[True] = DECLARED_MANUAL_IS_TEST_DATA
    corrected_by: str
    corrected_at: datetime
    correction_reason: str
    previous_declared_location: str | None
    new_declared_location: str | None
    previous_source_record_reference: str | None
    new_source_record_reference: str | None


class Step47PhaseADeclaredManualDetailRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    data_strength: Literal["declared_manual"] = DECLARED_MANUAL_DATA_STRENGTH
    is_legal_truth: Literal[False] = DECLARED_MANUAL_IS_LEGAL_TRUTH
    current_record: Step47PhaseADeclaredManualSourceRead
    original_record: Step47PhaseADeclaredManualSourceRead
    correction_trace: list[Step47PhaseADeclaredManualCorrectionTraceRead]


class Step47PhaseADeclaredManualListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    data_strength: Literal["declared_manual"] = DECLARED_MANUAL_DATA_STRENGTH
    is_legal_truth: Literal[False] = DECLARED_MANUAL_IS_LEGAL_TRUTH
    items: list[Step47PhaseADeclaredManualSourceRead]
    page: int
    page_size: int
    total_count: int
