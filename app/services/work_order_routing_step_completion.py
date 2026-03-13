from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.work_order_routing_step_eligibility import (
    WorkOrderExecutionEligibleRoutingStep,
    resolve_work_order_execution_eligible_routing_step,
)
from app.services.work_order_routing_step_transition import (
    WorkOrderExecutionEligibleRoutingStepTransition,
    validate_work_order_execution_routing_step_transition,
)


@dataclass(frozen=True)
class WorkOrderExecutionCompletionReadyRoutingStep:
    snapshot_id: int
    work_order_id: int
    current_step: WorkOrderExecutionEligibleRoutingStep
    target_step: WorkOrderExecutionEligibleRoutingStep
    completion_step: WorkOrderExecutionEligibleRoutingStep


def validate_work_order_execution_completion_ready_routing_step(
    db: Session,
    work_order_id: int,
    *,
    current_step_code: str | None = None,
    current_seq_no: int | None = None,
    target_step_code: str | None = None,
    target_seq_no: int | None = None,
    completion_step_code: str | None = None,
    completion_seq_no: int | None = None,
) -> WorkOrderExecutionCompletionReadyRoutingStep:
    transition = validate_work_order_execution_routing_step_transition(
        db=db,
        work_order_id=work_order_id,
        current_step_code=current_step_code,
        current_seq_no=current_seq_no,
        target_step_code=target_step_code,
        target_seq_no=target_seq_no,
    )

    completion_step = _resolve_completion_step(
        db=db,
        work_order_id=work_order_id,
        transition=transition,
        step_code=completion_step_code,
        seq_no=completion_seq_no,
    )

    if not _is_same_step(completion_step, transition.target_step):
        raise HTTPException(
            status_code=409,
            detail=(
                "WorkOrder routing step completion is not allowed: "
                f"completion target does not match resolved transition target in snapshot_id={transition.snapshot_id}: "
                f"target_seq_no={transition.target_step.seq_no}, completion_seq_no={completion_step.seq_no}"
            ),
        )

    return WorkOrderExecutionCompletionReadyRoutingStep(
        snapshot_id=transition.snapshot_id,
        work_order_id=transition.work_order_id,
        current_step=transition.current_step,
        target_step=transition.target_step,
        completion_step=completion_step,
    )


def _resolve_completion_step(
    *,
    db: Session,
    work_order_id: int,
    transition: WorkOrderExecutionEligibleRoutingStepTransition,
    step_code: str | None,
    seq_no: int | None,
) -> WorkOrderExecutionEligibleRoutingStep:
    if step_code is None and seq_no is None:
        return transition.target_step

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
                    "WorkOrder routing step completion is not allowed: "
                    f"invalid completion target: {exc.detail}"
                ),
            ) from exc
        raise


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
