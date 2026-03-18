from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.stock_ledger_fg_receive import FgReceiveLedgerPostRequest, StockLedgerFgReceiveResponse
from models import Product, RawMaterial, StockLedger, WorkOrder, WorkOrderFgReceive


SOURCE_EVENT_TYPE = "FG_RECEIVE"
MOVEMENT_TYPE = "IN"
STOCK_BUCKET = "FINISHED_GOODS"
LEGACY_TXN_TYPE = "RECEIPT"


def post_fg_receive_stock_ledger(
    db: Session,
    *,
    fg_receive_id: int,
    payload: FgReceiveLedgerPostRequest,
) -> StockLedgerFgReceiveResponse:
    normalized = _validate_post_input(payload)

    fg_receive = db.query(WorkOrderFgReceive).filter(WorkOrderFgReceive.id == fg_receive_id).first()
    if fg_receive is None:
        raise HTTPException(status_code=404, detail=f"FG receive not found: id={fg_receive_id}")

    if _status(fg_receive.receive_status) != "RECEIVED":
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive stock ledger posting requires RECEIVED status: "
                f"id={fg_receive.id}, receive_status={fg_receive.receive_status}"
            ),
        )

    _guard_duplicate_fg_receive_ledger_post(db=db, fg_receive_id=fg_receive.id)

    work_order, item_master = _resolve_inventory_subject(db=db, fg_receive=fg_receive)
    base_qty, base_uom = _resolve_base_quantity_and_uom(
        item_master=item_master,
        txn_qty=float(fg_receive.txn_qty),
        txn_uom=str(fg_receive.txn_uom or "").strip().upper(),
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
        qty=base_qty,
        uom=base_uom,
        txn_qty=float(fg_receive.txn_qty),
        txn_uom=str(fg_receive.txn_uom or "").strip().upper(),
        base_qty=base_qty,
        base_uom=base_uom,
        ref_type=SOURCE_EVENT_TYPE,
        ref_id=str(fg_receive.id),
        note=normalized["remark"],
        source_event_type=SOURCE_EVENT_TYPE,
        source_event_id=fg_receive.id,
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
            detail=f"FG receive stock ledger posting failed and rolled back: fg_receive_id={fg_receive.id}",
        )

    return _to_response(row)


def get_fg_receive_stock_ledger(
    db: Session,
    *,
    fg_receive_id: int,
) -> StockLedgerFgReceiveResponse:
    row = (
        db.query(StockLedger)
        .filter(StockLedger.source_event_type == SOURCE_EVENT_TYPE)
        .filter(StockLedger.source_event_id == fg_receive_id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"FG receive stock ledger not found: fg_receive_id={fg_receive_id}")
    return _to_response(row)


def _validate_post_input(payload: FgReceiveLedgerPostRequest) -> dict[str, str | None]:
    normalized = {
        "posted_by": str(payload.posted_by or "").strip(),
        "remark": _normalize_optional_text(payload.remark),
    }
    if not normalized["posted_by"]:
        raise HTTPException(status_code=409, detail="Invalid posted_by for FG receive stock ledger: posted_by is required")
    return normalized


def _guard_duplicate_fg_receive_ledger_post(*, db: Session, fg_receive_id: int) -> None:
    existing = (
        db.query(StockLedger)
        .filter(StockLedger.source_event_type == SOURCE_EVENT_TYPE)
        .filter(StockLedger.source_event_id == fg_receive_id)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate FG receive stock ledger posting is not allowed: fg_receive_id={fg_receive_id}",
        )


def _resolve_inventory_subject(*, db: Session, fg_receive: WorkOrderFgReceive) -> tuple[WorkOrder, RawMaterial]:
    work_order = db.query(WorkOrder).filter(WorkOrder.id == fg_receive.work_order_id).first()
    if work_order is None:
        raise HTTPException(
            status_code=409,
            detail=f"FG receive work order could not be resolved for stock ledger posting: fg_receive_id={fg_receive.id}",
        )

    product = db.query(Product).filter(Product.id == work_order.product_id).first()
    product_model_no = str(product.model_no or "").strip() if product is not None else ""
    if not product_model_no:
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive item resolution failed through work_order -> product.model_no -> RawMaterial.material_code: "
                f"fg_receive_id={fg_receive.id}, work_order_id={work_order.id}"
            ),
        )

    item_master = db.query(RawMaterial).filter(RawMaterial.material_code == product_model_no).first()
    if item_master is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive item resolution failed through work_order -> product.model_no -> RawMaterial.material_code: "
                f"fg_receive_id={fg_receive.id}, work_order_id={work_order.id}, product_model_no={product_model_no}"
            ),
        )

    return work_order, item_master


def _resolve_base_quantity_and_uom(*, item_master: RawMaterial, txn_qty: float, txn_uom: str) -> tuple[float, str]:
    base_uom = str(item_master.unit or "").strip().upper()
    if not base_uom:
        raise HTTPException(
            status_code=409,
            detail=f"FG receive stock ledger base_uom is missing for item_code={item_master.material_code}",
        )

    if txn_uom == base_uom:
        return txn_qty, base_uom

    conversion_type = str(item_master.conversion_type or "").strip().upper()
    if conversion_type != "STANDARD":
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive stock ledger conversion could not be resolved through SF-01: "
                f"item_code={item_master.material_code}, conversion_type={item_master.conversion_type}"
            ),
        )

    ratio = float(item_master.standard_conversion_ratio or 0)
    if ratio <= 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive stock ledger conversion could not be resolved through SF-01: "
                f"item_code={item_master.material_code}, standard_conversion_ratio={item_master.standard_conversion_ratio}"
            ),
        )

    return txn_qty * ratio, base_uom


def _format_ledger_no(row_id: int | None) -> str:
    if row_id is None:
        raise HTTPException(status_code=500, detail="FG receive stock ledger number could not be assigned")
    return f"SLED-{row_id:06d}"


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _status(value: str | None) -> str:
    return str(value or "").strip().upper()


def _to_response(row: StockLedger) -> StockLedgerFgReceiveResponse:
    return StockLedgerFgReceiveResponse(
        id=row.id,
        ledger_no=str(row.ledger_no or ""),
        source_event_type=str(row.source_event_type or ""),
        source_event_id=int(row.source_event_id),
        work_order_id=int(row.work_order_id),
        sales_order_id=row.sales_order_id,
        item_code=str(row.item_code or row.item_id or ""),
        movement_type=str(row.movement_type or ""),
        stock_bucket=str(row.stock_bucket or ""),
        txn_qty=float(row.txn_qty if row.txn_qty is not None else row.qty),
        txn_uom=str(row.txn_uom or row.uom or ""),
        base_qty=float(row.base_qty if row.base_qty is not None else row.qty),
        base_uom=str(row.base_uom or row.uom or ""),
        posted_at=row.posted_at or row.occurred_at,
        posted_by=str(row.posted_by or ""),
        remark=row.remark,
    )
