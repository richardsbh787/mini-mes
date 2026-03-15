from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import WorkOrderRoutingSnapshotStep
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
    started_by: str | None = None,
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
        snapshot_id=start_ready.snapshot_id,
    )

    if existing_active_step is not None and not _is_same_step(existing_active_step, candidate_step):
        raise HTTPException(
            status_code=409,
            detail="work order already has a different active step",
        )

    step_row = _load_snapshot_step_row(
        db=db,
        snapshot_id=start_ready.snapshot_id,
        seq_no=start_ready.start_step.seq_no,
        step_code=start_ready.start_step.step_code,
    )
    step_row.execution_status = "ACTIVE"
    if step_row.started_at is None:
        step_row.started_at = datetime.utcnow()
    if started_by is not None:
        step_row.started_by = started_by
    db.add(step_row)
    try:
        db.commit()
        db.refresh(step_row)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"WorkOrder routing step start failed and rolled back: work_order_id={work_order_id}",
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
    snapshot_id: int,
) -> WorkOrderExecutionEligibleRoutingStep | None:
    active_rows = (
        db.query(WorkOrderRoutingSnapshotStep)
        .filter(WorkOrderRoutingSnapshotStep.snapshot_id == snapshot_id)
        .filter(WorkOrderRoutingSnapshotStep.execution_status == "ACTIVE")
        .order_by(WorkOrderRoutingSnapshotStep.seq_no.asc(), WorkOrderRoutingSnapshotStep.id.asc())
        .all()
    )
    if not active_rows:
        return None
    if len(active_rows) > 1:
        raise HTTPException(
            status_code=409,
            detail=f"WorkOrder routing snapshot has multiple ACTIVE steps: snapshot_id={snapshot_id}",
        )
    row = active_rows[0]
    return WorkOrderExecutionEligibleRoutingStep(
        snapshot_id=snapshot_id,
        work_order_id=row.snapshot.work_order_id,
        seq_no=row.seq_no,
        step_code=row.step_code,
        step_name=row.step_name,
        department=row.department,
        is_required=row.is_required,
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
