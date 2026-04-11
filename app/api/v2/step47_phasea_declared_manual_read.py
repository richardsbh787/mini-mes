from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.schemas.step47_phasea_declared_manual import (
    Step47PhaseADeclaredManualDetailRead,
    Step47PhaseADeclaredManualListResponse,
)
from app.services.step47_phasea_declared_manual import (
    get_step47_phasea_declared_manual_source_detail,
    list_step47_phasea_declared_manual_source_read_surface,
)
from database import get_db


router = APIRouter(
    prefix="/v2/step47-phasea-declared-manual-records",
    tags=["v2-step47-phasea-declared-manual-read"],
)

STEP47_PHASEA_READ_ALLOWED_ENVS = {"dev", "development", "test"}
STEP47_PHASEA_READ_ENABLE_FLAG = "STEP47_PHASEA_DECLARED_MANUAL_READ_ENABLED"
MINI_MES_ENV_FLAG = "MINI_MES_ENV"


def _require_step47_phasea_declared_manual_read_boundary() -> None:
    current_env = os.getenv(MINI_MES_ENV_FLAG, "").strip().lower()
    read_enabled = os.getenv(STEP47_PHASEA_READ_ENABLE_FLAG, "").strip().lower() in {"1", "true", "yes", "on"}
    if current_env not in STEP47_PHASEA_READ_ALLOWED_ENVS or not read_enabled:
        raise HTTPException(
            status_code=404,
            detail="Step 47 Phase A declared/manual read surface is unavailable outside the approved dev/test boundary",
        )


@router.get("", response_model=Step47PhaseADeclaredManualListResponse)
def step47_phasea_declared_manual_record_list(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
    _: None = Depends(_require_step47_phasea_declared_manual_read_boundary),
    db: Session = Depends(get_db),
) -> Step47PhaseADeclaredManualListResponse:
    return list_step47_phasea_declared_manual_source_read_surface(
        db=db,
        page=page,
        page_size=page_size,
    )


@router.get("/detail", response_model=Step47PhaseADeclaredManualDetailRead)
def step47_phasea_declared_manual_record_detail(
    declaration_id: Annotated[int, Query(ge=1)],
    _: None = Depends(_require_step47_phasea_declared_manual_read_boundary),
    db: Session = Depends(get_db),
) -> Step47PhaseADeclaredManualDetailRead:
    return get_step47_phasea_declared_manual_source_detail(
        db=db,
        declaration_id=declaration_id,
    )
