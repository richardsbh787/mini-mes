from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from models import WorkOrderRoutingSnapshot


@dataclass(frozen=True)
class WorkOrderExecutionReadySnapshotStep:
    id: int
    seq_no: int
    step_code: str
    step_name: str
    department: str | None
    is_required: bool


@dataclass(frozen=True)
class WorkOrderExecutionReadySnapshot:
    snapshot_id: int
    work_order_id: int
    source_routing_id: int
    routing_code: str
    routing_name: str
    steps: tuple[WorkOrderExecutionReadySnapshotStep, ...]


def validate_work_order_execution_ready_snapshot(
    snapshot: WorkOrderRoutingSnapshot | None,
    *,
    work_order_id: int,
) -> WorkOrderExecutionReadySnapshot:
    if snapshot is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "WorkOrder has no routing snapshot and cannot resolve execution routing authority: "
                f"id={work_order_id}"
            ),
        )

    if snapshot.id is None:
        raise HTTPException(
            status_code=409,
            detail=f"WorkOrder routing snapshot is not execution-ready: missing snapshot_id for work_order_id={work_order_id}",
        )

    if snapshot.work_order_id is None:
        raise HTTPException(
            status_code=409,
            detail=f"WorkOrder routing snapshot is not execution-ready: missing work_order_id for snapshot_id={snapshot.id}",
        )

    if snapshot.source_routing_id is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "WorkOrder routing snapshot is not execution-ready: "
                f"missing source_routing_id for snapshot_id={snapshot.id}"
            ),
        )

    if not _has_text(snapshot.routing_code):
        raise HTTPException(
            status_code=409,
            detail=f"WorkOrder routing snapshot is not execution-ready: missing routing_code for snapshot_id={snapshot.id}",
        )

    if not _has_text(snapshot.routing_name):
        raise HTTPException(
            status_code=409,
            detail=f"WorkOrder routing snapshot is not execution-ready: missing routing_name for snapshot_id={snapshot.id}",
        )

    raw_steps = tuple(snapshot.steps)
    if not raw_steps:
        raise HTTPException(
            status_code=409,
            detail=f"WorkOrder routing snapshot is not execution-ready: snapshot has no steps: snapshot_id={snapshot.id}",
        )

    seen_seq_nos: set[int] = set()
    validated_steps: list[WorkOrderExecutionReadySnapshotStep] = []
    for step in raw_steps:
        if step.seq_no is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "WorkOrder routing snapshot is not execution-ready: "
                    f"snapshot step missing seq_no: snapshot_id={snapshot.id}, step_id={step.id}"
                ),
            )

        if step.seq_no in seen_seq_nos:
            raise HTTPException(
                status_code=409,
                detail=(
                    "WorkOrder routing snapshot is not execution-ready: "
                    f"duplicate seq_no={step.seq_no} in snapshot_id={snapshot.id}"
                ),
            )
        seen_seq_nos.add(step.seq_no)

        if not _has_text(step.step_code):
            raise HTTPException(
                status_code=409,
                detail=(
                    "WorkOrder routing snapshot is not execution-ready: "
                    f"snapshot step missing step_code: snapshot_id={snapshot.id}, step_id={step.id}"
                ),
            )

        if not _has_text(step.step_name):
            raise HTTPException(
                status_code=409,
                detail=(
                    "WorkOrder routing snapshot is not execution-ready: "
                    f"snapshot step missing step_name: snapshot_id={snapshot.id}, step_id={step.id}"
                ),
            )

        if step.is_required is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "WorkOrder routing snapshot is not execution-ready: "
                    f"snapshot step missing is_required: snapshot_id={snapshot.id}, step_id={step.id}"
                ),
            )

        validated_steps.append(
            WorkOrderExecutionReadySnapshotStep(
                id=step.id,
                seq_no=step.seq_no,
                step_code=step.step_code,
                step_name=step.step_name,
                department=step.department,
                is_required=step.is_required,
                )
            )

    ordered_validated_steps = tuple(sorted(validated_steps, key=lambda step: (step.seq_no, step.id)))

    return WorkOrderExecutionReadySnapshot(
        snapshot_id=snapshot.id,
        work_order_id=snapshot.work_order_id,
        source_routing_id=snapshot.source_routing_id,
        routing_code=snapshot.routing_code,
        routing_name=snapshot.routing_name,
        steps=ordered_validated_steps,
    )


def _has_text(value: str | None) -> bool:
    return value is not None and value.strip() != ""
