from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.step47_phasea_declared_manual import Step47PhaseADeclaredManualSourceRead
from app.schemas.step47_phasea_declared_manual_intake import (
    Step47PhaseADeclaredManualIntakeCreate,
    Step47PhaseADeclaredManualIntakeCreateResponse,
)
from models import Step47PhaseADeclaredManualSource


def create_step47_phasea_declared_manual_intake_record(
    db: Session,
    *,
    payload: Step47PhaseADeclaredManualIntakeCreate,
    authenticated_identity: str,
) -> Step47PhaseADeclaredManualIntakeCreateResponse:
    trusted_identity = str(authenticated_identity or "").strip()
    if not trusted_identity:
        raise HTTPException(
            status_code=401,
            detail="Step 47 Phase A declared/manual intake requires a trusted authenticated identity context",
        )

    row = Step47PhaseADeclaredManualSource(
        declared_by=trusted_identity,
        declared_location=payload.declared_location,
        source_record_reference=payload.source_record_reference,
    )
    db.add(row)
    db.flush()

    return Step47PhaseADeclaredManualIntakeCreateResponse(
        record=Step47PhaseADeclaredManualSourceRead.model_validate(row),
    )
