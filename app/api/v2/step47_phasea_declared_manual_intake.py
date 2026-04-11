from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.schemas.step47_phasea_declared_manual_intake import (
    Step47PhaseADeclaredManualIntakeCreate,
    Step47PhaseADeclaredManualIntakeCreateResponse,
)
from app.services.step47_phasea_declared_manual_intake import (
    create_step47_phasea_declared_manual_intake_record,
)
from database import get_db


router = APIRouter(
    prefix="/v2/step47-phasea-declared-manual-intake",
    tags=["v2-step47-phasea-declared-manual-intake"],
)

STEP47_PHASEA_INTAKE_ALLOWED_ENVS = {"dev", "development", "test"}
STEP47_PHASEA_INTAKE_ENABLE_FLAG = "STEP47_PHASEA_DECLARED_MANUAL_INTAKE_ENABLED"
MINI_MES_ENV_FLAG = "MINI_MES_ENV"
FORBIDDEN_CLIENT_FIELDS = {"declared_by", "declared_at"}
MISUSE_FIELDS = {
    "correction_target_id",
    "correction_mode",
    "overwrite_mode",
    "overwrite_target_id",
    "submission_mode",
}


def _require_step47_phasea_declared_manual_intake_boundary() -> None:
    current_env = os.getenv(MINI_MES_ENV_FLAG, "").strip().lower()
    intake_enabled = os.getenv(STEP47_PHASEA_INTAKE_ENABLE_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}
    if current_env not in STEP47_PHASEA_INTAKE_ALLOWED_ENVS or not intake_enabled:
        raise HTTPException(
            status_code=404,
            detail="Step 47 Phase A declared/manual intake is unavailable outside the approved dev/test boundary",
        )


def get_step47_phasea_declared_manual_authenticated_identity(request: Request) -> str:
    authenticated_identity = getattr(request.state, "step47_phasea_authenticated_identity", None)
    trusted_identity = str(authenticated_identity or "").strip()
    if not trusted_identity:
        raise HTTPException(
            status_code=401,
            detail="Step 47 Phase A declared/manual intake requires a trusted authenticated identity context",
        )
    return trusted_identity


def _reject_forbidden_client_fields(payload: dict[str, Any]) -> None:
    forbidden_fields = sorted(FORBIDDEN_CLIENT_FIELDS.intersection(payload.keys()))
    if forbidden_fields:
        raise HTTPException(
            status_code=422,
            detail=f"client-supplied field is forbidden for Step 47 Phase A declared/manual intake: {forbidden_fields[0]}",
        )


def _reject_misuse_flags(payload: dict[str, Any]) -> None:
    misuse_fields = sorted(MISUSE_FIELDS.intersection(payload.keys()))
    if misuse_fields:
        raise HTTPException(
            status_code=409,
            detail=(
                "Step 47 Phase A declared/manual intake is create-only and rejects overwrite/correction/submission misuse: "
                f"{misuse_fields[0]}"
            ),
        )


@router.post("", response_model=Step47PhaseADeclaredManualIntakeCreateResponse)
async def create_step47_phasea_declared_manual_intake(
    request: Request,
    _: None = Depends(_require_step47_phasea_declared_manual_intake_boundary),
    authenticated_identity: str = Depends(get_step47_phasea_declared_manual_authenticated_identity),
    db: Session = Depends(get_db),
) -> Step47PhaseADeclaredManualIntakeCreateResponse:
    raw_payload = await request.json()
    if isinstance(raw_payload, list):
        raise HTTPException(
            status_code=422,
            detail="Step 47 Phase A declared/manual intake accepts one record only and rejects bulk or array payloads",
        )
    if not isinstance(raw_payload, dict):
        raise HTTPException(
            status_code=422,
            detail="Step 47 Phase A declared/manual intake requires a single JSON object payload",
        )

    _reject_forbidden_client_fields(raw_payload)
    _reject_misuse_flags(raw_payload)
    try:
        payload = Step47PhaseADeclaredManualIntakeCreate.model_validate(raw_payload)
    except ValidationError as exc:
        first_error = exc.errors()[0]
        field_name = str(first_error["loc"][-1])
        raise HTTPException(status_code=422, detail=f"{field_name}: {first_error['msg']}") from exc
    return create_step47_phasea_declared_manual_intake_record(
        db=db,
        payload=payload,
        authenticated_identity=authenticated_identity,
    )
