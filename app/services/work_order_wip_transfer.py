from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from app.schemas.work_order_wip_transfer import (
    WorkOrderWipTransferCreateRequest,
    WorkOrderWipTransferResponse,
)
from models import Product, RawMaterial, WorkOrder, WorkOrderRoutingSnapshot, WorkOrderRoutingSnapshotStep, WorkOrderWipTransfer


ALLOWED_HANDLING_UNIT_TYPES = {"PALLET", "BUNDLE", "ROLL", "CARTON", "BIN", "TRAY", "LOOSE"}


def create_work_order_wip_transfer(
    db: Session,
    *,
    work_order_id: int,
    payload: WorkOrderWipTransferCreateRequest,
) -> WorkOrderWipTransferResponse:
    normalized = _validate_input(payload)

    work_order = (
        db.query(WorkOrder)
        .options(
            selectinload(WorkOrder.routing_snapshot).selectinload(WorkOrderRoutingSnapshot.steps),
            selectinload(WorkOrder.product),
        )
        .filter(WorkOrder.id == work_order_id)
        .first()
    )
    if not work_order:
        raise HTTPException(status_code=404, detail=f"WorkOrder not found: id={work_order_id}")

    snapshot = work_order.routing_snapshot
    if snapshot is None:
        raise HTTPException(
            status_code=409,
            detail=f"WorkOrder has no routing snapshot and cannot resolve execution routing authority: id={work_order_id}",
        )

    ordered_steps = sorted(snapshot.steps, key=lambda step: (step.seq_no, step.id))
    from_step = next((step for step in ordered_steps if step.seq_no == normalized["from_step_no"]), None)
    if from_step is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "WIP transfer from_step_no not found in routing snapshot: "
                f"snapshot_id={snapshot.id}, from_step_no={normalized['from_step_no']}"
            ),
        )

    to_step = next((step for step in ordered_steps if step.seq_no == normalized["to_step_no"]), None)
    if to_step is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "WIP transfer to_step_no not found in routing snapshot: "
                f"snapshot_id={snapshot.id}, to_step_no={normalized['to_step_no']}"
            ),
        )

    if _status(from_step.execution_status) != "DONE":
        raise HTTPException(
            status_code=409,
            detail=(
                "WIP transfer source step is not DONE: "
                f"snapshot_id={snapshot.id}, from_step_no={from_step.seq_no}, execution_status={from_step.execution_status}"
            ),
        )

    _validate_route_linkage(snapshot_id=snapshot.id, ordered_steps=ordered_steps, from_step=from_step, to_step=to_step)
    _validate_handling_unit(normalized["handling_unit_type"], normalized["handling_unit_label"])
    _validate_qty_and_uom(normalized["txn_qty"], normalized["txn_uom"])
    base_qty, base_uom = _resolve_base_quantity_and_uom(
        db=db,
        work_order=work_order,
        txn_qty=normalized["txn_qty"],
        txn_uom=normalized["txn_uom"],
    )
    _guard_duplicate_transfer(
        db=db,
        work_order_id=work_order.id,
        routing_snapshot_id=snapshot.id,
        from_step_no=from_step.seq_no,
        to_step_no=to_step.seq_no,
        handling_unit_type=normalized["handling_unit_type"],
        handling_unit_label=normalized["handling_unit_label"],
    )

    row = WorkOrderWipTransfer(
        transfer_no=_next_transfer_no(db=db, work_order_id=work_order.id),
        work_order_id=work_order.id,
        routing_snapshot_id=snapshot.id,
        from_step_no=from_step.seq_no,
        to_step_no=to_step.seq_no,
        handling_unit_type=normalized["handling_unit_type"],
        handling_unit_label=normalized["handling_unit_label"],
        txn_qty=normalized["txn_qty"],
        txn_uom=normalized["txn_uom"],
        base_qty=base_qty,
        base_uom=base_uom,
        transfer_status="CREATED",
        created_at=datetime.utcnow(),
        created_by=normalized["created_by"],
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"WIP transfer create failed and rolled back: work_order_id={work_order_id}",
        )

    return _to_response(row)


def list_work_order_wip_transfers(
    db: Session,
    *,
    work_order_id: int,
) -> list[WorkOrderWipTransferResponse]:
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail=f"WorkOrder not found: id={work_order_id}")

    rows = (
        db.query(WorkOrderWipTransfer)
        .filter(WorkOrderWipTransfer.work_order_id == work_order_id)
        .order_by(WorkOrderWipTransfer.id.asc())
        .all()
    )
    return [_to_response(row) for row in rows]


def get_work_order_wip_transfer(
    db: Session,
    *,
    transfer_id: int,
) -> WorkOrderWipTransferResponse:
    row = db.query(WorkOrderWipTransfer).filter(WorkOrderWipTransfer.id == transfer_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"WIP transfer not found: id={transfer_id}")
    return _to_response(row)


def _validate_input(payload: WorkOrderWipTransferCreateRequest) -> dict[str, object]:
    normalized = {
        "from_step_no": payload.from_step_no,
        "to_step_no": payload.to_step_no,
        "handling_unit_type": str(payload.handling_unit_type or "").strip().upper(),
        "handling_unit_label": _normalize_optional_text(payload.handling_unit_label),
        "txn_qty": float(payload.txn_qty),
        "txn_uom": str(payload.txn_uom or "").strip().upper(),
        "created_by": str(payload.created_by or "").strip(),
    }
    if normalized["from_step_no"] <= 0:
        raise HTTPException(status_code=409, detail="Invalid from_step_no for WIP transfer: from_step_no must be > 0")
    if normalized["to_step_no"] <= 0:
        raise HTTPException(status_code=409, detail="Invalid to_step_no for WIP transfer: to_step_no must be > 0")
    if not normalized["created_by"]:
        raise HTTPException(status_code=409, detail="Invalid created_by for WIP transfer: created_by is required")
    return normalized


def _validate_route_linkage(
    *,
    snapshot_id: int,
    ordered_steps: list[WorkOrderRoutingSnapshotStep],
    from_step: WorkOrderRoutingSnapshotStep,
    to_step: WorkOrderRoutingSnapshotStep,
) -> None:
    next_steps = [step for step in ordered_steps if step.seq_no > from_step.seq_no]
    expected_next_step = next_steps[0] if next_steps else None
    if expected_next_step is None or expected_next_step.seq_no != to_step.seq_no:
        raise HTTPException(
            status_code=409,
            detail=(
                "WIP transfer route linkage is invalid: "
                f"snapshot_id={snapshot_id}, from_step_no={from_step.seq_no}, to_step_no={to_step.seq_no}"
            ),
        )


def _validate_handling_unit(handling_unit_type: str, handling_unit_label: str | None) -> None:
    if handling_unit_type not in ALLOWED_HANDLING_UNIT_TYPES:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid handling_unit_type for WIP transfer: handling_unit_type={handling_unit_type}",
        )
    if handling_unit_type != "LOOSE" and handling_unit_label is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Invalid handling unit label for WIP transfer: "
                f"handling_unit_type={handling_unit_type} requires handling_unit_label"
            ),
        )


def _validate_qty_and_uom(txn_qty: float, txn_uom: str) -> None:
    if txn_qty <= 0:
        raise HTTPException(status_code=409, detail="Invalid txn_qty for WIP transfer: txn_qty must be > 0")
    if not txn_uom:
        raise HTTPException(status_code=409, detail="Invalid txn_uom for WIP transfer: txn_uom is required")


def _resolve_base_quantity_and_uom(
    *,
    db: Session,
    work_order: WorkOrder,
    txn_qty: float,
    txn_uom: str,
) -> tuple[float, str]:
    product = db.query(Product).filter(Product.id == work_order.product_id).first()
    product_code = str(product.model_no or "").strip() if product is not None else ""
    item_master = None
    if product_code:
        item_master = db.query(RawMaterial).filter(RawMaterial.material_code == product_code).first()

    if item_master is None:
        return txn_qty, txn_uom

    base_uom = str(item_master.unit or "").strip().upper()
    if not base_uom:
        raise HTTPException(
            status_code=409,
            detail=f"WIP transfer item master base_uom is missing for item_code={product_code}",
        )

    if txn_uom == base_uom:
        return txn_qty, base_uom

    conversion_type = str(item_master.conversion_type or "").strip().upper()
    if conversion_type != "STANDARD":
        raise HTTPException(
            status_code=409,
            detail=(
                "WIP transfer conversion could not be resolved through SF-01: "
                f"item_code={product_code}, conversion_type={item_master.conversion_type}"
            ),
        )

    ratio = float(item_master.standard_conversion_ratio or 0)
    if ratio <= 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "WIP transfer conversion could not be resolved through SF-01: "
                f"item_code={product_code}, standard_conversion_ratio={item_master.standard_conversion_ratio}"
            ),
        )

    return txn_qty * ratio, base_uom


def _guard_duplicate_transfer(
    *,
    db: Session,
    work_order_id: int,
    routing_snapshot_id: int,
    from_step_no: int,
    to_step_no: int,
    handling_unit_type: str,
    handling_unit_label: str | None,
) -> None:
    existing = (
        db.query(WorkOrderWipTransfer)
        .filter(WorkOrderWipTransfer.work_order_id == work_order_id)
        .filter(WorkOrderWipTransfer.routing_snapshot_id == routing_snapshot_id)
        .filter(WorkOrderWipTransfer.from_step_no == from_step_no)
        .filter(WorkOrderWipTransfer.to_step_no == to_step_no)
        .filter(WorkOrderWipTransfer.handling_unit_type == handling_unit_type)
        .filter(
            (WorkOrderWipTransfer.handling_unit_label == handling_unit_label)
            if handling_unit_label is not None
            else (WorkOrderWipTransfer.handling_unit_label.is_(None))
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Duplicate WIP transfer is not allowed: "
                f"work_order_id={work_order_id}, from_step_no={from_step_no}, to_step_no={to_step_no}, "
                f"handling_unit_type={handling_unit_type}, handling_unit_label={handling_unit_label}"
            ),
        )


def _next_transfer_no(*, db: Session, work_order_id: int) -> str:
    count = db.query(WorkOrderWipTransfer).filter(WorkOrderWipTransfer.work_order_id == work_order_id).count()
    return f"WIPT-{work_order_id}-{count + 1:04d}"


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _status(value: str | None) -> str:
    return str(value or "").strip().upper()


def _to_response(row: WorkOrderWipTransfer) -> WorkOrderWipTransferResponse:
    return WorkOrderWipTransferResponse(
        id=row.id,
        transfer_no=row.transfer_no,
        work_order_id=row.work_order_id,
        routing_snapshot_id=row.routing_snapshot_id,
        from_step_no=row.from_step_no,
        to_step_no=row.to_step_no,
        handling_unit_type=row.handling_unit_type,
        handling_unit_label=row.handling_unit_label,
        txn_qty=row.txn_qty,
        txn_uom=row.txn_uom,
        base_qty=row.base_qty,
        base_uom=row.base_uom,
        transfer_status=row.transfer_status,
        created_at=row.created_at,
        created_by=row.created_by,
    )
