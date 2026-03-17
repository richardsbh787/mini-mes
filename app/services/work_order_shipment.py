from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.schemas.work_order_shipment import WorkOrderShipmentCreateRequest, WorkOrderShipmentResponse
from models import WorkOrder, WorkOrderFgReceive, WorkOrderShipment


ALLOWED_SHIPMENT_STATUS = {"SHIPPED"}


def create_work_order_shipment(
    db: Session,
    *,
    work_order_id: int,
    payload: WorkOrderShipmentCreateRequest,
) -> WorkOrderShipmentResponse:
    normalized = _validate_input(payload)

    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if work_order is None:
        raise HTTPException(status_code=404, detail=f"WorkOrder not found: id={work_order_id}")

    fg_receive = db.query(WorkOrderFgReceive).filter(WorkOrderFgReceive.id == normalized["fg_receive_id"]).first()
    if fg_receive is None:
        raise HTTPException(status_code=404, detail=f"FG receive not found: id={normalized['fg_receive_id']}")

    if fg_receive.work_order_id != work_order.id:
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive does not belong to work order shipment context: "
                f"work_order_id={work_order.id}, fg_receive_id={fg_receive.id}"
            ),
        )

    if _status(fg_receive.receive_status) != "RECEIVED":
        raise HTTPException(
            status_code=409,
            detail=(
                "Shipment requires RECEIVED FG receive: "
                f"id={fg_receive.id}, receive_status={fg_receive.receive_status}"
            ),
        )

    _validate_qty_and_uom(txn_qty=normalized["txn_qty"], txn_uom=normalized["txn_uom"], fg_receive=fg_receive)

    cumulative_shipped_qty = _get_cumulative_shipped_qty(db=db, fg_receive_id=fg_receive.id)

    if cumulative_shipped_qty + normalized["txn_qty"] > fg_receive.txn_qty:
        raise HTTPException(
            status_code=409,
            detail=(
                "Shipment qty exceeds remaining shippable qty from FG receive: "
                f"fg_receive_id={fg_receive.id}, received_qty={fg_receive.txn_qty}, "
                f"already_shipped_qty={cumulative_shipped_qty}, requested_qty={normalized['txn_qty']}"
            ),
        )

    _validate_shipment_ref(normalized["shipment_ref"])

    row = WorkOrderShipment(
        shipment_no=_next_shipment_no(db=db, work_order_id=work_order.id),
        work_order_id=work_order.id,
        sales_order_id=work_order.sales_order_id,
        fg_receive_id=fg_receive.id,
        txn_qty=normalized["txn_qty"],
        txn_uom=normalized["txn_uom"],
        shipment_ref=normalized["shipment_ref"],
        shipment_remark=normalized["shipment_remark"],
        shipment_status="SHIPPED",
        shipped_at=datetime.utcnow(),
        shipped_by=normalized["shipped_by"],
    )
    db.add(row)
    try:
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=(
                "Shipment create failed and rolled back: "
                f"work_order_id={work_order_id}, fg_receive_id={fg_receive.id}"
            ),
        )

    return _to_response(row)


def list_work_order_shipments(
    db: Session,
    *,
    work_order_id: int,
) -> list[WorkOrderShipmentResponse]:
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if work_order is None:
        raise HTTPException(status_code=404, detail=f"WorkOrder not found: id={work_order_id}")

    rows = (
        db.query(WorkOrderShipment)
        .filter(WorkOrderShipment.work_order_id == work_order_id)
        .order_by(WorkOrderShipment.id.asc())
        .all()
    )
    return [_to_response(row) for row in rows]


def get_work_order_shipment(
    db: Session,
    *,
    shipment_id: int,
) -> WorkOrderShipmentResponse:
    row = db.query(WorkOrderShipment).filter(WorkOrderShipment.id == shipment_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Shipment not found: id={shipment_id}")
    return _to_response(row)


def _validate_input(payload: WorkOrderShipmentCreateRequest) -> dict[str, object]:
    normalized = {
        "fg_receive_id": int(payload.fg_receive_id),
        "txn_qty": float(payload.txn_qty),
        "txn_uom": str(payload.txn_uom or "").strip().upper(),
        "shipment_ref": str(payload.shipment_ref or "").strip(),
        "shipment_remark": _normalize_optional_text(payload.shipment_remark),
        "shipped_by": str(payload.shipped_by or "").strip(),
    }
    if normalized["fg_receive_id"] <= 0:
        raise HTTPException(status_code=409, detail="Invalid fg_receive_id for shipment: fg_receive_id must be > 0")
    if not normalized["shipped_by"]:
        raise HTTPException(status_code=409, detail="Invalid shipped_by for shipment: shipped_by is required")
    return normalized


def _validate_qty_and_uom(*, txn_qty: float, txn_uom: str, fg_receive: WorkOrderFgReceive) -> None:
    if txn_qty <= 0:
        raise HTTPException(status_code=409, detail="Invalid txn_qty for shipment: txn_qty must be > 0")
    if not txn_uom:
        raise HTTPException(status_code=409, detail="Invalid txn_uom for shipment: txn_uom is required")
    if _status(txn_uom) != _status(fg_receive.txn_uom):
        raise HTTPException(
            status_code=409,
            detail=(
                "Shipment txn_uom must match FG receive txn_uom: "
                f"fg_receive_id={fg_receive.id}, shipment.txn_uom={txn_uom}, fg_receive.txn_uom={fg_receive.txn_uom}"
            ),
        )


def _get_cumulative_shipped_qty(*, db: Session, fg_receive_id: int) -> float:
    total = (
        db.query(func.coalesce(func.sum(WorkOrderShipment.txn_qty), 0.0))
        .filter(WorkOrderShipment.fg_receive_id == fg_receive_id)
        .scalar()
    )
    return float(total or 0.0)


def _validate_shipment_ref(shipment_ref: str) -> None:
    if not shipment_ref:
        raise HTTPException(status_code=409, detail="Invalid shipment_ref for shipment: shipment_ref is required")


def _next_shipment_no(*, db: Session, work_order_id: int) -> str:
    count = db.query(WorkOrderShipment).filter(WorkOrderShipment.work_order_id == work_order_id).count()
    return f"SHP-{work_order_id}-{count + 1:04d}"


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _status(value: str | None) -> str:
    return str(value or "").strip().upper()


def _to_response(row: WorkOrderShipment) -> WorkOrderShipmentResponse:
    shipment_status = _status(row.shipment_status)
    if shipment_status not in ALLOWED_SHIPMENT_STATUS:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid shipment_status stored for shipment: id={row.id}, shipment_status={row.shipment_status}",
        )

    return WorkOrderShipmentResponse(
        id=row.id,
        shipment_no=row.shipment_no,
        work_order_id=row.work_order_id,
        sales_order_id=row.sales_order_id,
        fg_receive_id=row.fg_receive_id,
        txn_qty=row.txn_qty,
        txn_uom=row.txn_uom,
        shipment_ref=row.shipment_ref,
        shipment_remark=row.shipment_remark,
        shipment_status=shipment_status,
        shipped_at=row.shipped_at,
        shipped_by=row.shipped_by,
    )
