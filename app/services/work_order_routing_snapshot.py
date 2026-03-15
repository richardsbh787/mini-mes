from __future__ import annotations

from sqlalchemy.orm import Session

from models import RoutingHeader, WorkOrder, WorkOrderRoutingSnapshot, WorkOrderRoutingSnapshotStep


def create_work_order_routing_snapshot(db: Session, work_order: WorkOrder, routing: RoutingHeader) -> WorkOrderRoutingSnapshot:
    snapshot = WorkOrderRoutingSnapshot(
        work_order_id=work_order.id,
        source_routing_id=routing.id,
        routing_code=routing.routing_code,
        routing_name=routing.routing_name,
    )
    db.add(snapshot)
    db.flush()

    ordered_steps = sorted(routing.steps, key=lambda step: (step.seq_no, step.id))
    for step in ordered_steps:
        db.add(
            WorkOrderRoutingSnapshotStep(
                snapshot_id=snapshot.id,
                seq_no=step.seq_no,
                step_code=step.step_code,
                step_name=step.step_name,
                department=step.department,
                is_required=step.is_required,
                execution_status="PENDING",
                started_at=None,
                started_by=None,
                completed_at=None,
                completed_by=None,
            )
        )

    db.flush()
    return snapshot
