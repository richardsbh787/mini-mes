from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.work_order_routing_step_active import (
    WorkOrderExecutionSnapshotActiveStep,
    guard_work_order_routing_snapshot_active_step,
)
from app.services.work_order_routing_step_completion import (
    validate_work_order_execution_completion_ready_routing_step,
)
from app.services.work_order_routing_step_eligibility import (
    WorkOrderExecutionEligibleRoutingStep,
    resolve_work_order_execution_eligible_routing_step,
)


@dataclass(frozen=True)
class WorkOrderExecutionSnapshotActiveStepRelease:
    snapshot_id: int
    work_order_id: int
    release_target_step: WorkOrderExecutionEligibleRoutingStep
    current_active_step: WorkOrderExecutionEligibleRoutingStep
    release_allowed: bool
    resulting_active_step: None
    has_active_step: bool


def guard_work_order_routing_snapshot_active_step_release(
    db: Session,
    work_order_id: int,
    *,
    current_step_code: str | None = None,
    current_seq_no: int | None = None,
    target_step_code: str | None = None,
    target_seq_no: int | None = None,
    release_step_code: str | None = None,
    release_seq_no: int | None = None,
    active_step_code: str | None = None,
    active_seq_no: int | None = None,
    existing_active_step_code: str | None = None,
    existing_active_seq_no: int | None = None,
) -> WorkOrderExecutionSnapshotActiveStepRelease:
    release_target_step = _resolve_explicit_release_target(
        db=db,
        work_order_id=work_order_id,
        step_code=release_step_code,
        seq_no=release_seq_no,
    )

    completion_ready = validate_work_order_execution_completion_ready_routing_step(
        db=db,
        work_order_id=work_order_id,
        current_step_code=current_step_code,
        current_seq_no=current_seq_no,
        target_step_code=target_step_code,
        target_seq_no=target_seq_no,
        completion_step_code=release_target_step.step_code,
        completion_seq_no=release_target_step.seq_no,
    )

    active_step = _resolve_current_active_step(
        db=db,
        work_order_id=work_order_id,
        active_step_code=active_step_code,
        active_seq_no=active_seq_no,
        existing_active_step_code=existing_active_step_code,
        existing_active_seq_no=existing_active_seq_no,
    )

    if not _is_same_step(release_target_step, active_step.active_step):
        raise HTTPException(
            status_code=409,
            detail="active step release target does not match current active step",
        )

    return WorkOrderExecutionSnapshotActiveStepRelease(
        snapshot_id=completion_ready.snapshot_id,
        work_order_id=completion_ready.work_order_id,
        release_target_step=completion_ready.completion_step,
        current_active_step=active_step.active_step,
        release_allowed=True,
        resulting_active_step=None,
        has_active_step=False,
    )


def _resolve_explicit_release_target(
    *,
    db: Session,
    work_order_id: int,
    step_code: str | None,
    seq_no: int | None,
) -> WorkOrderExecutionEligibleRoutingStep:
    if step_code is None and seq_no is None:
        raise HTTPException(status_code=409, detail="active step release target must be explicit")

    return resolve_work_order_execution_eligible_routing_step(
        db=db,
        work_order_id=work_order_id,
        step_code=step_code,
        seq_no=seq_no,
    )


def _resolve_current_active_step(
    *,
    db: Session,
    work_order_id: int,
    active_step_code: str | None,
    active_seq_no: int | None,
    existing_active_step_code: str | None,
    existing_active_seq_no: int | None,
) -> WorkOrderExecutionSnapshotActiveStep:
    return guard_work_order_routing_snapshot_active_step(
        db=db,
        work_order_id=work_order_id,
        current_step_code=active_step_code,
        current_seq_no=active_seq_no,
        target_step_code=active_step_code,
        target_seq_no=active_seq_no,
        active_step_code=active_step_code,
        active_seq_no=active_seq_no,
        existing_active_step_code=existing_active_step_code,
        existing_active_seq_no=existing_active_seq_no,
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
