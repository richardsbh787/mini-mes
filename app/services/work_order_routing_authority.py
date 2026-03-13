from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from models import WorkOrder, WorkOrderRoutingSnapshot
from app.services.work_order_routing_readiness import validate_work_order_execution_ready_snapshot


@dataclass(frozen=True)
class WorkOrderExecutionRoutingStepAuthority:
    seq_no: int
    step_code: str
    step_name: str
    department: str | None
    is_required: bool


@dataclass(frozen=True)
class WorkOrderExecutionRoutingAuthority:
    work_order_id: int
    snapshot_id: int
    source_routing_id: int
    routing_code: str
    routing_name: str
    steps: tuple[WorkOrderExecutionRoutingStepAuthority, ...]


def resolve_work_order_execution_routing_authority(
    db: Session,
    work_order_id: int,
) -> WorkOrderExecutionRoutingAuthority:
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

    ordered_steps = tuple(
        WorkOrderExecutionRoutingStepAuthority(
            seq_no=step.seq_no,
            step_code=step.step_code,
            step_name=step.step_name,
            department=step.department,
            is_required=step.is_required,
        )
        for step in ready_snapshot.steps
    )

    return WorkOrderExecutionRoutingAuthority(
        work_order_id=work_order.id,
        snapshot_id=ready_snapshot.snapshot_id,
        source_routing_id=ready_snapshot.source_routing_id,
        routing_code=ready_snapshot.routing_code,
        routing_name=ready_snapshot.routing_name,
        steps=ordered_steps,
    )
