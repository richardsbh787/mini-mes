from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.work_order_routing_step_eligibility import (
    WorkOrderExecutionEligibleRoutingStep,
    resolve_work_order_execution_eligible_routing_step,
)
from app.services.work_order_routing_step_start import (
    WorkOrderExecutionStartReadyRoutingStep,
    validate_work_order_execution_start_ready_routing_step,
)


@dataclass(frozen=True)
class WorkOrderExecutionSnapshotActiveStep:
    snapshot_id: int
    work_order_id: int
    current_step: WorkOrderExecutionEligibleRoutingStep
    target_step: WorkOrderExecutionEligibleRoutingStep
    active_step: WorkOrderExecutionEligibleRoutingStep
    existing_active_step: WorkOrderExecutionEligibleRoutingStep | None


def guard_work_order_routing_snapshot_active_step(
    db: Session,
    work_order_id: int,
    *,
    current_step_code: str | None = None,
    current_seq_no: int | None = None,
    target_step_code: str | None = None,
    target_seq_no: int | None = None,
    active_step_code: str | None = None,
    active_seq_no: int | None = None,
    existing_active_step_code: str | None = None,
    existing_active_seq_no: int | None = None,
) -> WorkOrderExecutionSnapshotActiveStep:
    candidate_step = _resolve_explicit_active_step_candidate(
        db=db,
        work_order_id=work_order_id,
        step_code=active_step_code,
        seq_no=active_seq_no,
    )

    start_ready = validate_work_order_execution_start_ready_routing_step(
        db=db,
        work_order_id=work_order_id,
        current_step_code=current_step_code,
        current_seq_no=current_seq_no,
        target_step_code=target_step_code,
        target_seq_no=target_seq_no,
        start_step_code=candidate_step.step_code,
        start_seq_no=candidate_step.seq_no,
    )

    existing_active_step = _resolve_existing_active_step(
        db=db,
        work_order_id=work_order_id,
        step_code=existing_active_step_code,
        seq_no=existing_active_seq_no,
    )

    if existing_active_step is not None and not _is_same_step(existing_active_step, candidate_step):
        raise HTTPException(
            status_code=409,
            detail="work order already has a different active step",
        )

    return WorkOrderExecutionSnapshotActiveStep(
        snapshot_id=start_ready.snapshot_id,
        work_order_id=start_ready.work_order_id,
        current_step=start_ready.current_step,
        target_step=start_ready.target_step,
        active_step=start_ready.start_step,
        existing_active_step=existing_active_step,
    )


def _resolve_explicit_active_step_candidate(
    *,
    db: Session,
    work_order_id: int,
    step_code: str | None,
    seq_no: int | None,
) -> WorkOrderExecutionEligibleRoutingStep:
    if step_code is None and seq_no is None:
        raise HTTPException(status_code=409, detail="active step must be explicit")

    return resolve_work_order_execution_eligible_routing_step(
        db=db,
        work_order_id=work_order_id,
        step_code=step_code,
        seq_no=seq_no,
    )


def _resolve_existing_active_step(
    *,
    db: Session,
    work_order_id: int,
    step_code: str | None,
    seq_no: int | None,
) -> WorkOrderExecutionEligibleRoutingStep | None:
    if step_code is None and seq_no is None:
        return None

    return resolve_work_order_execution_eligible_routing_step(
        db=db,
        work_order_id=work_order_id,
        step_code=step_code,
        seq_no=seq_no,
    )


def _is_same_step(
    left: WorkOrderExecutionEligibleRoutingStep,
    right: WorkOrderExecutionEligibleRoutingStep,
) -> bool:
    return (
        left.snapshot_id == right.snapshot_id
        and left.work_order_id == right.work_order_id
        and left.seq_no == right.seq_no
        and left.step_code == right.step_code
    )
