from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import WorkOrderRoutingSnapshotStep
from app.services.work_order_routing_step_active import (
    WorkOrderExecutionSnapshotActiveStep,
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
    completed_by: str | None = None,
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
        snapshot_id=completion_ready.snapshot_id,
    )

    if not _is_same_step(release_target_step, active_step.active_step):
        raise HTTPException(
            status_code=409,
            detail="active step release target does not match current active step",
        )

    step_row = _load_snapshot_step_row(
        db=db,
        snapshot_id=completion_ready.snapshot_id,
        seq_no=completion_ready.completion_step.seq_no,
        step_code=completion_ready.completion_step.step_code,
    )
    step_row.execution_status = "DONE"
    step_row.completed_at = datetime.utcnow()
    if completed_by is not None:
        step_row.completed_by = completed_by
    db.add(step_row)
    try:
        db.commit()
        db.refresh(step_row)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"WorkOrder routing step release failed and rolled back: work_order_id={work_order_id}",
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
    snapshot_id: int,
) -> WorkOrderExecutionSnapshotActiveStep:
    active_rows = (
        db.query(WorkOrderRoutingSnapshotStep)
        .filter(WorkOrderRoutingSnapshotStep.snapshot_id == snapshot_id)
        .filter(WorkOrderRoutingSnapshotStep.execution_status == "ACTIVE")
        .order_by(WorkOrderRoutingSnapshotStep.seq_no.asc(), WorkOrderRoutingSnapshotStep.id.asc())
        .all()
    )
    if len(active_rows) != 1:
        raise HTTPException(
            status_code=409,
            detail="active step release target does not match current active step",
        )
    row = active_rows[0]
    active_step = WorkOrderExecutionEligibleRoutingStep(
        snapshot_id=snapshot_id,
        work_order_id=row.snapshot.work_order_id,
        seq_no=row.seq_no,
        step_code=row.step_code,
        step_name=row.step_name,
        department=row.department,
        is_required=row.is_required,
    )
    return WorkOrderExecutionSnapshotActiveStep(
        snapshot_id=snapshot_id,
        work_order_id=row.snapshot.work_order_id,
        current_step=active_step,
        target_step=active_step,
        active_step=active_step,
        existing_active_step=active_step,
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


def _load_snapshot_step_row(
    *,
    db: Session,
    snapshot_id: int,
    seq_no: int,
    step_code: str,
) -> WorkOrderRoutingSnapshotStep:
    row = (
        db.query(WorkOrderRoutingSnapshotStep)
        .filter(WorkOrderRoutingSnapshotStep.snapshot_id == snapshot_id)
        .filter(WorkOrderRoutingSnapshotStep.seq_no == seq_no)
        .filter(WorkOrderRoutingSnapshotStep.step_code == step_code)
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=409,
            detail=(
                "WorkOrder routing snapshot step truth row not found: "
                f"snapshot_id={snapshot_id}, seq_no={seq_no}, step_code={step_code}"
            ),
        )
    return row
