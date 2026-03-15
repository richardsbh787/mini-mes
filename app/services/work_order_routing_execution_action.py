from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import WorkOrderRoutingSnapshotStep
from app.services.work_order_routing_authority import resolve_work_order_execution_routing_authority
from app.schemas.work_order_routing_execution_action import (
    WorkOrderRoutingExecutionActionActiveStateSummary,
    WorkOrderRoutingExecutionActionResponse,
    WorkOrderRoutingExecutionActionStep,
)
from app.services.work_order_routing_step_active import (
    WorkOrderExecutionSnapshotActiveStep,
    guard_work_order_routing_snapshot_active_step,
)
from app.services.work_order_routing_step_active_release import (
    WorkOrderExecutionSnapshotActiveStepRelease,
    guard_work_order_routing_snapshot_active_step_release,
)
from app.services.work_order_routing_step_eligibility import WorkOrderExecutionEligibleRoutingStep


def start_work_order_routing_execution_action(
    db: Session,
    *,
    work_order_id: int,
    step_code: str | None,
    seq_no: int | None,
    started_by: str,
) -> WorkOrderRoutingExecutionActionResponse:
    current_step = _derive_start_current_step(db=db, work_order_id=work_order_id)
    result = guard_work_order_routing_snapshot_active_step(
        db=db,
        work_order_id=work_order_id,
        current_step_code=current_step.step_code,
        current_seq_no=current_step.seq_no,
        target_step_code=step_code,
        target_seq_no=seq_no,
        active_step_code=step_code,
        active_seq_no=seq_no,
        started_by=started_by,
    )
    return _build_start_response(result)


def release_work_order_routing_execution_action(
    db: Session,
    *,
    work_order_id: int,
    step_code: str | None,
    seq_no: int | None,
    completed_by: str,
) -> WorkOrderRoutingExecutionActionResponse:
    current_active_step = _derive_current_active_step(db=db, work_order_id=work_order_id)
    result = guard_work_order_routing_snapshot_active_step_release(
        db=db,
        work_order_id=work_order_id,
        current_step_code=current_active_step.step_code,
        current_seq_no=current_active_step.seq_no,
        target_step_code=step_code,
        target_seq_no=seq_no,
        release_step_code=step_code,
        release_seq_no=seq_no,
        completed_by=completed_by,
    )
    return _build_release_response(result)


def _build_start_response(
    result: WorkOrderExecutionSnapshotActiveStep,
) -> WorkOrderRoutingExecutionActionResponse:
    active_step = _build_step(result.active_step)
    return WorkOrderRoutingExecutionActionResponse(
        work_order_id=result.work_order_id,
        routing_snapshot_id=result.snapshot_id,
        affected_step=active_step,
        active_state=WorkOrderRoutingExecutionActionActiveStateSummary(
            has_active_step=True,
            active_step=active_step,
        ),
        execution_status="ACTIVE",
    )


def _build_release_response(
    result: WorkOrderExecutionSnapshotActiveStepRelease,
) -> WorkOrderRoutingExecutionActionResponse:
    return WorkOrderRoutingExecutionActionResponse(
        work_order_id=result.work_order_id,
        routing_snapshot_id=result.snapshot_id,
        affected_step=_build_step(result.release_target_step),
        active_state=WorkOrderRoutingExecutionActionActiveStateSummary(
            has_active_step=result.has_active_step,
            active_step=None,
        ),
        execution_status="DONE",
    )


def _build_step(step: object) -> WorkOrderRoutingExecutionActionStep:
    return WorkOrderRoutingExecutionActionStep(
        seq_no=step.seq_no,
        step_code=step.step_code,
        step_name=step.step_name,
        department=step.department,
        is_required=step.is_required,
    )


def _derive_start_current_step(
    *,
    db: Session,
    work_order_id: int,
) -> WorkOrderExecutionEligibleRoutingStep:
    authority = resolve_work_order_execution_routing_authority(db=db, work_order_id=work_order_id)
    rows = _load_snapshot_truth_rows(db=db, snapshot_id=authority.snapshot_id)

    active_rows = [row for row in rows if _normalized_status(row.execution_status) == "ACTIVE"]
    if len(active_rows) > 1:
        raise HTTPException(
            status_code=409,
            detail=f"WorkOrder routing snapshot has multiple ACTIVE steps: snapshot_id={authority.snapshot_id}",
        )
    if len(active_rows) == 1:
        return _build_eligible_step(authority=authority, step_row=active_rows[0])

    done_rows = [row for row in rows if _normalized_status(row.execution_status) == "DONE"]
    if done_rows:
        return _build_eligible_step(authority=authority, step_row=done_rows[-1])

    return _build_eligible_step(authority=authority, step_row=rows[0])


def _derive_current_active_step(
    *,
    db: Session,
    work_order_id: int,
) -> WorkOrderExecutionEligibleRoutingStep:
    authority = resolve_work_order_execution_routing_authority(db=db, work_order_id=work_order_id)
    rows = _load_snapshot_truth_rows(db=db, snapshot_id=authority.snapshot_id)
    active_rows = [row for row in rows if _normalized_status(row.execution_status) == "ACTIVE"]

    if len(active_rows) != 1:
        raise HTTPException(
            status_code=409,
            detail="active step release target does not match current active step",
        )

    return _build_eligible_step(authority=authority, step_row=active_rows[0])


def _load_snapshot_truth_rows(
    *,
    db: Session,
    snapshot_id: int,
) -> list[WorkOrderRoutingSnapshotStep]:
    rows = (
        db.query(WorkOrderRoutingSnapshotStep)
        .filter(WorkOrderRoutingSnapshotStep.snapshot_id == snapshot_id)
        .order_by(WorkOrderRoutingSnapshotStep.seq_no.asc(), WorkOrderRoutingSnapshotStep.id.asc())
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=409,
            detail=f"WorkOrder routing snapshot is not execution-ready: snapshot has no steps: snapshot_id={snapshot_id}",
        )
    return rows


def _build_eligible_step(
    *,
    authority: object,
    step_row: WorkOrderRoutingSnapshotStep,
) -> WorkOrderExecutionEligibleRoutingStep:
    return WorkOrderExecutionEligibleRoutingStep(
        snapshot_id=authority.snapshot_id,
        work_order_id=authority.work_order_id,
        seq_no=step_row.seq_no,
        step_code=step_row.step_code,
        step_name=step_row.step_name,
        department=step_row.department,
        is_required=step_row.is_required,
    )


def _normalized_status(status: str | None) -> str:
    return str(status or "").strip().upper()
