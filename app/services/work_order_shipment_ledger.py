from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.stock_ledger_shipment import ShipmentLedgerPostRequest, StockLedgerShipmentResponse
from models import Product, RawMaterial, StockLedger, WorkOrder, WorkOrderFgReceive, WorkOrderShipment


SOURCE_EVENT_TYPE = "SHIPMENT"
MOVEMENT_TYPE = "OUT"
STOCK_BUCKET = "FINISHED_GOODS"
LEGACY_TXN_TYPE = "ISSUE"


def post_shipment_stock_ledger(
    db: Session,
    *,
    shipment_id: int,
    payload: ShipmentLedgerPostRequest,
) -> StockLedgerShipmentResponse:
    normalized = _validate_post_input(payload)

    shipment = db.query(WorkOrderShipment).filter(WorkOrderShipment.id == shipment_id).first()
    if shipment is None:
        raise HTTPException(status_code=404, detail=f"Shipment not found: id={shipment_id}")

    if _status(shipment.shipment_status) != "SHIPPED":
        raise HTTPException(
            status_code=409,
            detail=(
                "Shipment stock ledger posting requires SHIPPED status: "
                f"id={shipment.id}, shipment_status={shipment.shipment_status}"
            ),
        )

    _guard_duplicate_shipment_ledger_post(db=db, shipment_id=shipment.id)

    work_order, fg_receive, item_master = _resolve_inventory_subject(db=db, shipment=shipment)
    base_qty, base_uom = _resolve_base_quantity_and_uom(
        item_master=item_master,
        txn_qty=float(shipment.txn_qty),
        txn_uom=str(shipment.txn_uom or "").strip().upper(),
    )

    posted_at = datetime.utcnow()
    item_code = str(item_master.material_code).strip()
    row = StockLedger(
        org_id="demo-org",
        ledger_no="PENDING",
        item_id=item_code,
        item_code=item_code,
        location_id=None,
        txn_type=LEGACY_TXN_TYPE,
        movement_type=MOVEMENT_TYPE,
        stock_bucket=STOCK_BUCKET,
        qty=0 - base_qty,
        uom=base_uom,
        txn_qty=float(shipment.txn_qty),
        txn_uom=str(shipment.txn_uom or "").strip().upper(),
        base_qty=base_qty,
        base_uom=base_uom,
        ref_type=SOURCE_EVENT_TYPE,
        ref_id=str(shipment.id),
        note=normalized["remark"],
        source_event_type=SOURCE_EVENT_TYPE,
        source_event_id=shipment.id,
        work_order_id=work_order.id,
        sales_order_id=work_order.sales_order_id,
        work_order_no=work_order.work_order_no,
        posted_by=normalized["posted_by"],
        remark=normalized["remark"],
        posted_at=posted_at,
        occurred_at=posted_at,
    )
    db.add(row)
    try:
        db.flush()
        row.ledger_no = _format_ledger_no(row.id)
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Shipment stock ledger posting failed and rolled back: shipment_id={shipment.id}",
        )

    return _to_response(row)


def get_shipment_stock_ledger(
    db: Session,
    *,
    shipment_id: int,
) -> StockLedgerShipmentResponse:
    row = (
        db.query(StockLedger)
        .filter(StockLedger.source_event_type == SOURCE_EVENT_TYPE)
        .filter(StockLedger.source_event_id == shipment_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"Shipment stock ledger not found: shipment_id={shipment_id}")
    return _to_response(row)


def _validate_post_input(payload: ShipmentLedgerPostRequest) -> dict[str, str | None]:
    normalized = {
        "posted_by": str(payload.posted_by or "").strip(),
        "remark": _normalize_optional_text(payload.remark),
    }
    if not normalized["posted_by"]:
        raise HTTPException(status_code=409, detail="Invalid posted_by for shipment stock ledger: posted_by is required")
    return normalized


def _guard_duplicate_shipment_ledger_post(*, db: Session, shipment_id: int) -> None:
    existing = (
        db.query(StockLedger)
        .filter(StockLedger.source_event_type == SOURCE_EVENT_TYPE)
        .filter(StockLedger.source_event_id == shipment_id)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate shipment stock ledger posting is not allowed: shipment_id={shipment_id}",
        )


def _resolve_inventory_subject(
    *,
    db: Session,
    shipment: WorkOrderShipment,
) -> tuple[WorkOrder, WorkOrderFgReceive, RawMaterial]:
    fg_receive = db.query(WorkOrderFgReceive).filter(WorkOrderFgReceive.id == shipment.fg_receive_id).first()
    if fg_receive is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Shipment item resolution failed through shipment -> shipment.fg_receive_id -> "
                "WorkOrderFgReceive -> work_order -> product.model_no -> RawMaterial.material_code: "
                f"shipment_id={shipment.id}, fg_receive_id={shipment.fg_receive_id}"
            ),
        )

    work_order = db.query(WorkOrder).filter(WorkOrder.id == fg_receive.work_order_id).first()
    if work_order is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Shipment work order could not be resolved through shipment.fg_receive_id linkage: "
                f"shipment_id={shipment.id}, fg_receive_id={fg_receive.id}"
            ),
        )

    product = db.query(Product).filter(Product.id == work_order.product_id).first()
    product_model_no = str(product.model_no or "").strip() if product is not None else ""
    if not product_model_no:
        raise HTTPException(
            status_code=409,
            detail=(
                "Shipment item resolution failed through shipment -> shipment.fg_receive_id -> "
                "WorkOrderFgReceive -> work_order -> product.model_no -> RawMaterial.material_code: "
                f"shipment_id={shipment.id}, fg_receive_id={fg_receive.id}, work_order_id={work_order.id}"
            ),
        )

    item_master = db.query(RawMaterial).filter(RawMaterial.material_code == product_model_no).first()
    if item_master is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Shipment item resolution failed through shipment -> shipment.fg_receive_id -> "
                "WorkOrderFgReceive -> work_order -> product.model_no -> RawMaterial.material_code: "
                f"shipment_id={shipment.id}, fg_receive_id={fg_receive.id}, work_order_id={work_order.id}, "
                f"product_model_no={product_model_no}"
            ),
        )

    return work_order, fg_receive, item_master


def _resolve_base_quantity_and_uom(*, item_master: RawMaterial, txn_qty: float, txn_uom: str) -> tuple[float, str]:
    base_uom = str(item_master.unit or "").strip().upper()
    if not base_uom:
        raise HTTPException(
            status_code=409,
            detail=f"Shipment stock ledger base_uom is missing for item_code={item_master.material_code}",
        )

    if txn_uom == base_uom:
        return txn_qty, base_uom

    conversion_type = str(item_master.conversion_type or "").strip().upper()
    if conversion_type != "STANDARD":
        raise HTTPException(
            status_code=409,
            detail=(
                "Shipment stock ledger conversion could not be resolved through SF-01: "
                f"item_code={item_master.material_code}, conversion_type={item_master.conversion_type}"
            ),
        )

    ratio = float(item_master.standard_conversion_ratio or 0)
    if ratio <= 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "Shipment stock ledger conversion could not be resolved through SF-01: "
                f"item_code={item_master.material_code}, standard_conversion_ratio={item_master.standard_conversion_ratio}"
            ),
        )

    return txn_qty * ratio, base_uom


def _format_ledger_no(row_id: int | None) -> str:
    if row_id is None:
        raise HTTPException(status_code=500, detail="Shipment stock ledger number could not be assigned")
    return f"SLED-{row_id:06d}"


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _status(value: str | None) -> str:
    return str(value or "").strip().upper()


def _to_response(row: StockLedger) -> StockLedgerShipmentResponse:
    return StockLedgerShipmentResponse(
        id=row.id,
        ledger_no=str(row.ledger_no or ""),
        source_event_type=str(row.source_event_type or ""),
        source_event_id=int(row.source_event_id),
        work_order_id=int(row.work_order_id),
        sales_order_id=row.sales_order_id,
        item_code=str(row.item_code or row.item_id or ""),
        movement_type=str(row.movement_type or ""),
        stock_bucket=str(row.stock_bucket or ""),
        txn_qty=float(row.txn_qty if row.txn_qty is not None else abs(row.qty)),
        txn_uom=str(row.txn_uom or row.uom or ""),
        base_qty=float(row.base_qty if row.base_qty is not None else abs(row.qty)),
        base_uom=str(row.base_uom or row.uom or ""),
        posted_at=row.posted_at or row.occurred_at,
        posted_by=str(row.posted_by or ""),
        remark=row.remark,
    )
