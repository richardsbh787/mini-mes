from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.work_order_routing_authority import resolve_work_order_execution_routing_authority
from app.services.work_order_routing_step_eligibility import (
    WorkOrderExecutionEligibleRoutingStep,
    resolve_work_order_execution_eligible_routing_step,
)


@dataclass(frozen=True)
class WorkOrderExecutionEligibleRoutingStepTransition:
    snapshot_id: int
    work_order_id: int
    current_step: WorkOrderExecutionEligibleRoutingStep
    target_step: WorkOrderExecutionEligibleRoutingStep


def validate_work_order_execution_routing_step_transition(
    db: Session,
    work_order_id: int,
    *,
    current_step_code: str | None = None,
    current_seq_no: int | None = None,
    target_step_code: str | None = None,
    target_seq_no: int | None = None,
) -> WorkOrderExecutionEligibleRoutingStepTransition:
    current_step = _resolve_transition_step(
        db=db,
        work_order_id=work_order_id,
        step_role="current",
        step_code=current_step_code,
        seq_no=current_seq_no,
    )
    target_step = _resolve_transition_step(
        db=db,
        work_order_id=work_order_id,
        step_role="target",
        step_code=target_step_code,
        seq_no=target_seq_no,
    )

    if current_step.snapshot_id != target_step.snapshot_id:
        raise HTTPException(
            status_code=409,
            detail=(
                "WorkOrder routing step transition is not allowed: "
                f"current and target steps do not belong to the same snapshot for work_order_id={work_order_id}"
            ),
        )

    authority = resolve_work_order_execution_routing_authority(db=db, work_order_id=work_order_id)

    if target_step.seq_no < current_step.seq_no:
        raise HTTPException(
            status_code=409,
            detail=(
                "WorkOrder routing step transition is not allowed: "
                f"backward transition in snapshot_id={authority.snapshot_id}: "
                f"current_seq_no={current_step.seq_no}, target_seq_no={target_step.seq_no}"
            ),
        )

    if target_step.seq_no > current_step.seq_no:
        skipped_required_steps = tuple(
            step
            for step in authority.steps
            if current_step.seq_no < step.seq_no < target_step.seq_no and step.is_required
        )
        if skipped_required_steps:
            skipped_seq_nos = ", ".join(str(step.seq_no) for step in skipped_required_steps)
            raise HTTPException(
                status_code=409,
                detail=(
                    "WorkOrder routing step transition is not allowed: "
                    f"forward transition skips required snapshot step(s) in snapshot_id={authority.snapshot_id}: "
                    f"skipped_seq_no={skipped_seq_nos}"
                ),
            )

    return WorkOrderExecutionEligibleRoutingStepTransition(
        snapshot_id=authority.snapshot_id,
        work_order_id=authority.work_order_id,
        current_step=current_step,
        target_step=target_step,
    )


def _resolve_transition_step(
    *,
    db: Session,
    work_order_id: int,
    step_role: str,
    step_code: str | None,
    seq_no: int | None,
) -> WorkOrderExecutionEligibleRoutingStep:
    try:
        return resolve_work_order_execution_eligible_routing_step(
            db=db,
            work_order_id=work_order_id,
            step_code=step_code,
            seq_no=seq_no,
        )
    except HTTPException as exc:
        if exc.status_code == 409 and isinstance(exc.detail, str) and exc.detail.startswith(
            "WorkOrder routing step target is not execution-eligible:"
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "WorkOrder routing step transition is not allowed: "
                    f"invalid {step_role} step target: {exc.detail}"
                ),
            ) from exc
        raise
