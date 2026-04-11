from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.step47_phasea_declared_manual import (
    DECLARED_MANUAL_DATA_STRENGTH,
    DECLARED_MANUAL_IS_LEGAL_TRUTH,
    Step47PhaseADeclaredManualSourceRead,
    normalize_declared_location,
    normalize_required_text,
)


class Step47PhaseADeclaredManualIntakeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    declared_location: str = Field(min_length=1)
    source_record_reference: str = Field(min_length=1)

    @model_validator(mode="after")
    def normalize_fields(self) -> "Step47PhaseADeclaredManualIntakeCreate":
        self.declared_location = normalize_declared_location(self.declared_location)
        self.source_record_reference = normalize_required_text(
            self.source_record_reference,
            field_name="source_record_reference",
        )
        return self


class Step47PhaseADeclaredManualIntakeCreateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    data_strength: Literal["declared_manual"] = DECLARED_MANUAL_DATA_STRENGTH
    is_legal_truth: Literal[False] = DECLARED_MANUAL_IS_LEGAL_TRUTH
    record: Step47PhaseADeclaredManualSourceRead
