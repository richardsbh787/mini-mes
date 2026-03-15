from __future__ import annotations

from collections.abc import Sequence

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from models import WorkOrder, WorkOrderRoutingSnapshot, WorkOrderRoutingSnapshotStep
from app.schemas.work_order_routing_execution_read import (
    WorkOrderRoutingExecutionReadResponse,
    WorkOrderRoutingExecutionReadStep,
)
from app.services.work_order_routing_readiness import validate_work_order_execution_ready_snapshot


def build_work_order_routing_execution_read(
    db: Session,
    work_order_id: int,
) -> WorkOrderRoutingExecutionReadResponse:
    work_order = (
        db.query(WorkOrder)
        .options(selectinload(WorkOrder.routing_snapshot).selectinload(WorkOrderRoutingSnapshot.steps))
        .filter(WorkOrder.id == work_order_id)
        .first()
    )
    if not work_order:
        raise HTTPException(status_code=404, detail=f"WorkOrder not found: id={work_order_id}")

    ready_snapshot = validate_work_order_execution_ready_snapshot(
        work_order.routing_snapshot,
        work_order_id=work_order_id,
    )

    raw_steps_by_id = {
        step.id: step
        for step in work_order.routing_snapshot.steps
    }
    ordered_steps: list[WorkOrderRoutingExecutionReadStep] = []
    active_steps: list[WorkOrderRoutingExecutionReadStep] = []

    for snapshot_step in ready_snapshot.steps:
        raw_step = raw_steps_by_id.get(snapshot_step.id)
        if raw_step is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "WorkOrder routing snapshot step truth row not found: "
                    f"snapshot_id={ready_snapshot.snapshot_id}, step_id={snapshot_step.id}"
                ),
            )

        step_status = _validate_execution_status(
            raw_step,
            snapshot_id=ready_snapshot.snapshot_id,
        )
        read_step = WorkOrderRoutingExecutionReadStep(
            seq_no=snapshot_step.seq_no,
            step_code=snapshot_step.step_code,
            step_name=snapshot_step.step_name,
            department=snapshot_step.department,
            is_required=snapshot_step.is_required,
            step_status=step_status,
        )
        ordered_steps.append(read_step)
        if step_status == "ACTIVE":
            active_steps.append(read_step)

    if len(active_steps) > 1:
        raise HTTPException(
            status_code=409,
            detail=f"WorkOrder routing snapshot has multiple ACTIVE steps: snapshot_id={ready_snapshot.snapshot_id}",
        )

    active_step = active_steps[0] if active_steps else None

    return WorkOrderRoutingExecutionReadResponse(
        work_order_id=work_order.id,
        work_order_no=work_order.work_order_no,
        routing_snapshot_id=ready_snapshot.snapshot_id,
        routing_code=ready_snapshot.routing_code,
        routing_name=ready_snapshot.routing_name,
        has_active_step=active_step is not None,
        is_routing_completed=derive_work_order_routing_completed(ordered_steps),
        active_step=active_step,
        steps=ordered_steps,
    )


def derive_work_order_routing_completed(
    steps: Sequence[WorkOrderRoutingExecutionReadStep],
) -> bool:
    has_active_step = any(step.step_status == "ACTIVE" for step in steps)
    has_required_not_done = any(
        step.is_required and step.step_status != "DONE"
        for step in steps
    )
    return not has_active_step and not has_required_not_done


def _validate_execution_status(
    step: WorkOrderRoutingSnapshotStep,
    *,
    snapshot_id: int,
) -> str:
    status = str(step.execution_status or "").strip().upper()
    if status not in {"PENDING", "ACTIVE", "DONE"}:
        raise HTTPException(
            status_code=409,
            detail=(
                "WorkOrder routing snapshot has invalid execution_status: "
                f"snapshot_id={snapshot_id}, step_id={step.id}, execution_status={step.execution_status}"
            ),
        )
    return status
