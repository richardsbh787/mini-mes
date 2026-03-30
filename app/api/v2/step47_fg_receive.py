from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.step47_fg_receive import (
    FgReceiveResolutionDetailRead,
    FgReceiveResolutionListItem,
    FgReceiveResolutionSummaryRead,
    FgReceiveStep47ExecuteRequest,
    FgReceiveStep47ExecuteResponse,
)
from app.services.step47_fg_receive import (
    execute_fg_receive_step47,
    get_fg_receive_step47_resolution_detail,
    list_fg_receive_step47_resolution_cases,
    summarize_fg_receive_step47_resolution,
)
from database import get_db


router = APIRouter(prefix="/v2/fg-receive-step47", tags=["v2-fg-receive-step47"])


@router.post("/{fg_receive_id}/execute", response_model=FgReceiveStep47ExecuteResponse)
def fg_receive_step47_execute(
    fg_receive_id: int,
    payload: FgReceiveStep47ExecuteRequest,
    db: Session = Depends(get_db),
):
    return execute_fg_receive_step47(db=db, fg_receive_id=fg_receive_id, payload=payload)


@router.get("/list", response_model=list[FgReceiveResolutionListItem])
def fg_receive_step47_list(
    outcome_class: str | None = None,
    has_final_truth: bool | None = None,
    has_evidence_snapshot: bool | None = None,
    db: Session = Depends(get_db),
):
    return list_fg_receive_step47_resolution_cases(
        db=db,
        outcome_class=outcome_class,
        has_final_truth=has_final_truth,
        has_evidence_snapshot=has_evidence_snapshot,
    )


@router.get("/summary", response_model=FgReceiveResolutionSummaryRead)
def fg_receive_step47_summary(db: Session = Depends(get_db)):
    return summarize_fg_receive_step47_resolution(db=db)


@router.get("/{fg_receive_id}", response_model=FgReceiveResolutionDetailRead)
def fg_receive_step47_detail(
    fg_receive_id: int,
    db: Session = Depends(get_db),
):
    return get_fg_receive_step47_resolution_detail(db=db, fg_receive_id=fg_receive_id)
