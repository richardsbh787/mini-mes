from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.schemas.work_order_fg_receive import WorkOrderFgReceiveCreateRequest, WorkOrderFgReceiveResponse
from models import WorkOrder, WorkOrderFgReceive, WorkOrderRoutingSnapshot, WorkOrderWipTransfer


ALLOWED_FG_HANDLING_UNIT_TYPES = {"PALLET", "CARTON", "BIN", "LOOSE"}


def create_work_order_fg_receive(
    db: Session,
    *,
    work_order_id: int,
    payload: WorkOrderFgReceiveCreateRequest,
) -> WorkOrderFgReceiveResponse:
    normalized = _validate_input(payload)

    work_order = (
        db.query(WorkOrder)
        .options(selectinload(WorkOrder.routing_snapshot).selectinload(WorkOrderRoutingSnapshot.steps))
        .filter(WorkOrder.id == work_order_id)
        .first()
    )
    if work_order is None:
        raise HTTPException(status_code=404, detail=f"WorkOrder not found: id={work_order_id}")

    transfer = db.query(WorkOrderWipTransfer).filter(WorkOrderWipTransfer.id == normalized["wip_transfer_id"]).first()
    if transfer is None:
        raise HTTPException(status_code=404, detail=f"WIP transfer not found: id={normalized['wip_transfer_id']}")

    if transfer.work_order_id != work_order.id:
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive transfer does not belong to work order: "
                f"work_order_id={work_order.id}, wip_transfer_id={transfer.id}"
            ),
        )

    if _status(transfer.transfer_status) != "RELEASED":
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive requires RELEASED WIP transfer: "
                f"id={transfer.id}, transfer_status={transfer.transfer_status}"
            ),
        )

    _validate_final_routing_output_eligibility(work_order=work_order, transfer=transfer)
    _validate_fg_handling_unit(normalized["fg_handling_unit_type"], normalized["fg_handling_unit_label"])
    _validate_qty_and_uom(normalized["txn_qty"], normalized["txn_uom"])
    _guard_duplicate_fg_receive(db=db, wip_transfer_id=transfer.id)

    row = WorkOrderFgReceive(
        fg_receive_no=_next_fg_receive_no(db=db, work_order_id=work_order.id),
        work_order_id=work_order.id,
        wip_transfer_id=transfer.id,
        routing_snapshot_id=transfer.routing_snapshot_id,
        fg_handling_unit_type=normalized["fg_handling_unit_type"],
        fg_handling_unit_label=normalized["fg_handling_unit_label"],
        txn_qty=normalized["txn_qty"],
        txn_uom=normalized["txn_uom"],
        receive_status="RECEIVED",
        received_at=datetime.utcnow(),
        received_by=normalized["received_by"],
        remark=normalized["remark"],
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"FG receive create failed and rolled back: work_order_id={work_order_id}, wip_transfer_id={transfer.id}",
        )

    return _to_response(row)


def list_work_order_fg_receipts(
    db: Session,
    *,
    work_order_id: int,
) -> list[WorkOrderFgReceiveResponse]:
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if work_order is None:
        raise HTTPException(status_code=404, detail=f"WorkOrder not found: id={work_order_id}")

    rows = (
        db.query(WorkOrderFgReceive)
        .filter(WorkOrderFgReceive.work_order_id == work_order_id)
        .order_by(WorkOrderFgReceive.id.asc())
        .all()
    )
    return [_to_response(row) for row in rows]


def get_work_order_fg_receive(
    db: Session,
    *,
    fg_receive_id: int,
) -> WorkOrderFgReceiveResponse:
    row = db.query(WorkOrderFgReceive).filter(WorkOrderFgReceive.id == fg_receive_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"FG receive not found: id={fg_receive_id}")
    return _to_response(row)


def _validate_input(payload: WorkOrderFgReceiveCreateRequest) -> dict[str, object]:
    normalized = {
        "wip_transfer_id": int(payload.wip_transfer_id),
        "fg_handling_unit_type": str(payload.fg_handling_unit_type or "").strip().upper(),
        "fg_handling_unit_label": _normalize_optional_text(payload.fg_handling_unit_label),
        "txn_qty": float(payload.txn_qty),
        "txn_uom": str(payload.txn_uom or "").strip().upper(),
        "received_by": str(payload.received_by or "").strip(),
        "remark": _normalize_optional_text(payload.remark),
    }
    if normalized["wip_transfer_id"] <= 0:
        raise HTTPException(status_code=409, detail="Invalid wip_transfer_id for FG receive: wip_transfer_id must be > 0")
    if not normalized["received_by"]:
        raise HTTPException(status_code=409, detail="Invalid received_by for FG receive: received_by is required")
    return normalized


def _validate_final_routing_output_eligibility(*, work_order: WorkOrder, transfer: WorkOrderWipTransfer) -> None:
    snapshot = work_order.routing_snapshot
    if snapshot is None:
        raise HTTPException(
            status_code=409,
            detail=f"WorkOrder has no routing snapshot and cannot validate FG receive final output eligibility: id={work_order.id}",
        )
    if transfer.routing_snapshot_id != snapshot.id:
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive transfer routing snapshot mismatch: "
                f"work_order_id={work_order.id}, wip_transfer_id={transfer.id}, "
                f"transfer.routing_snapshot_id={transfer.routing_snapshot_id}, work_order.routing_snapshot_id={snapshot.id}"
            ),
        )

    ordered_steps = sorted(snapshot.steps, key=lambda step: (step.seq_no, step.id))
    final_step = ordered_steps[-1] if ordered_steps else None
    if final_step is None:
        raise HTTPException(
            status_code=409,
            detail=f"WorkOrder routing snapshot has no steps and cannot validate FG receive final output eligibility: snapshot_id={snapshot.id}",
        )
    if transfer.to_step_no != final_step.seq_no:
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive requires final-routing-output transfer: "
                f"wip_transfer_id={transfer.id}, to_step_no={transfer.to_step_no}, final_step_no={final_step.seq_no}"
            ),
        )
    if _status(transfer.qc_decision) != "PASS" or not _is_available_for_next_step(transfer):
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive requires QC-passed available transfer: "
                f"id={transfer.id}, qc_decision={transfer.qc_decision}, transfer_status={transfer.transfer_status}"
            ),
        )
    if _status(final_step.execution_status) != "DONE":
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive requires completed final routing step: "
                f"snapshot_id={snapshot.id}, final_step_no={final_step.seq_no}, execution_status={final_step.execution_status}"
            ),
        )


def _validate_fg_handling_unit(fg_handling_unit_type: str, fg_handling_unit_label: str | None) -> None:
    if fg_handling_unit_type not in ALLOWED_FG_HANDLING_UNIT_TYPES:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid fg_handling_unit_type for FG receive: fg_handling_unit_type={fg_handling_unit_type}",
        )
    if fg_handling_unit_type != "LOOSE" and fg_handling_unit_label is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Invalid FG handling unit label for FG receive: "
                f"fg_handling_unit_type={fg_handling_unit_type} requires fg_handling_unit_label"
            ),
        )


def _validate_qty_and_uom(txn_qty: float, txn_uom: str) -> None:
    if txn_qty <= 0:
        raise HTTPException(status_code=409, detail="Invalid txn_qty for FG receive: txn_qty must be > 0")
    if not txn_uom:
        raise HTTPException(status_code=409, detail="Invalid txn_uom for FG receive: txn_uom is required")


def _guard_duplicate_fg_receive(*, db: Session, wip_transfer_id: int) -> None:
    existing = db.query(WorkOrderFgReceive).filter(WorkOrderFgReceive.wip_transfer_id == wip_transfer_id).first()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate FG receive is not allowed: wip_transfer_id={wip_transfer_id}",
        )


def _next_fg_receive_no(*, db: Session, work_order_id: int) -> str:
    count = db.query(WorkOrderFgReceive).filter(WorkOrderFgReceive.work_order_id == work_order_id).count()
    return f"FGR-{work_order_id}-{count + 1:04d}"


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _status(value: str | None) -> str:
    return str(value or "").strip().upper()


def _is_available_for_next_step(transfer: WorkOrderWipTransfer) -> bool:
    return _status(transfer.transfer_status) == "RELEASED" and _status(transfer.qc_decision) == "PASS"


def _to_response(row: WorkOrderFgReceive) -> WorkOrderFgReceiveResponse:
    return WorkOrderFgReceiveResponse(
        id=row.id,
        fg_receive_no=row.fg_receive_no,
        work_order_id=row.work_order_id,
        wip_transfer_id=row.wip_transfer_id,
        routing_snapshot_id=row.routing_snapshot_id,
        fg_handling_unit_type=row.fg_handling_unit_type,
        fg_handling_unit_label=row.fg_handling_unit_label,
        txn_qty=row.txn_qty,
        txn_uom=row.txn_uom,
        receive_status=row.receive_status,
        received_at=row.received_at,
        received_by=row.received_by,
        remark=row.remark,
    )
