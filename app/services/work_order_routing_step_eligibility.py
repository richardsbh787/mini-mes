from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.work_order_routing_authority import (
    WorkOrderExecutionRoutingStepAuthority,
    resolve_work_order_execution_routing_authority,
)


@dataclass(frozen=True)
class WorkOrderExecutionEligibleRoutingStep:
    snapshot_id: int
    work_order_id: int
    seq_no: int
    step_code: str
    step_name: str
    department: str | None
    is_required: bool


def resolve_work_order_execution_eligible_routing_step(
    db: Session,
    work_order_id: int,
    *,
    step_code: str | None = None,
    seq_no: int | None = None,
) -> WorkOrderExecutionEligibleRoutingStep:
    if step_code is None and seq_no is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "WorkOrder routing step target is not execution-eligible: "
                f"step_code and seq_no are both absent for work_order_id={work_order_id}"
            ),
        )

    authority = resolve_work_order_execution_routing_authority(db=db, work_order_id=work_order_id)

    matched_steps = authority.steps
    if step_code is not None:
        matched_steps = tuple(step for step in matched_steps if step.step_code == step_code)
        if not matched_steps:
            raise HTTPException(
                status_code=409,
                detail=(
                    "WorkOrder routing step target is not execution-eligible: "
                    f"step_code not found in snapshot_id={authority.snapshot_id}: step_code={step_code}"
                ),
            )

    if seq_no is not None:
        prefiltered_steps = matched_steps
        matched_steps = tuple(step for step in matched_steps if step.seq_no == seq_no)
        if not matched_steps:
            if step_code is not None and prefiltered_steps:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "WorkOrder routing step target is not execution-eligible: "
                        f"step_code and seq_no do not identify the same snapshot step in snapshot_id={authority.snapshot_id}: "
                        f"step_code={step_code}, seq_no={seq_no}"
                    ),
                )
            raise HTTPException(
                status_code=409,
                detail=(
                    "WorkOrder routing step target is not execution-eligible: "
                    f"seq_no not found in snapshot_id={authority.snapshot_id}: seq_no={seq_no}"
                ),
            )

    if step_code is not None and seq_no is None and len(matched_steps) > 1:
        raise HTTPException(
            status_code=409,
            detail=(
                "WorkOrder routing step target is not execution-eligible: "
                f"step_code resolves to multiple snapshot steps in snapshot_id={authority.snapshot_id}: "
                f"step_code={step_code}"
            ),
        )

    matched_step = _require_unique_match(
        matched_steps,
        snapshot_id=authority.snapshot_id,
        step_code=step_code,
        seq_no=seq_no,
    )

    return WorkOrderExecutionEligibleRoutingStep(
        snapshot_id=authority.snapshot_id,
        work_order_id=authority.work_order_id,
        seq_no=matched_step.seq_no,
        step_code=matched_step.step_code,
        step_name=matched_step.step_name,
        department=matched_step.department,
        is_required=matched_step.is_required,
    )


def _require_unique_match(
    matched_steps: tuple[WorkOrderExecutionRoutingStepAuthority, ...],
    *,
    snapshot_id: int,
    step_code: str | None,
    seq_no: int | None,
) -> WorkOrderExecutionRoutingStepAuthority:
    if len(matched_steps) != 1:
        target_parts: list[str] = []
        if step_code is not None:
            target_parts.append(f"step_code={step_code}")
        if seq_no is not None:
            target_parts.append(f"seq_no={seq_no}")

        raise HTTPException(
            status_code=409,
            detail=(
                "WorkOrder routing step target is not execution-eligible: "
                f"target does not resolve to exactly one snapshot step in snapshot_id={snapshot_id}: "
                + ", ".join(target_parts)
            ),
        )

    return matched_steps[0]
