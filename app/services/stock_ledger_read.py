from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.stock_ledger_read import (
    StockLedgerBalanceReadResponse,
    StockLedgerEntryReadResponse,
)
from models import StockLedger


ALLOWED_STOCK_BUCKETS = {"RAW_MATERIAL", "FINISHED_GOODS"}
ALLOWED_MOVEMENT_TYPES = {"IN", "OUT"}
ALLOWED_SOURCE_EVENT_TYPES = {"FG_RECEIVE", "SHIPMENT", "RM_ISSUE"}


def list_stock_ledger_balance(
    db: Session,
    *,
    org_id: str,
    item_code: str | None = None,
    stock_bucket: str | None = None,
    source_event_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[StockLedgerBalanceReadResponse]:
    normalized_item_code = _normalize_optional_text(item_code)
    normalized_stock_bucket = _validate_enum(
        name="stock_bucket",
        value=stock_bucket,
        allowed_values=ALLOWED_STOCK_BUCKETS,
    )
    normalized_source_event_type = _validate_enum(
        name="source_event_type",
        value=source_event_type,
        allowed_values=ALLOWED_SOURCE_EVENT_TYPES,
    )
    _validate_date_range(date_from=date_from, date_to=date_to)

    rows = _query_rows(
        db=db,
        org_id=org_id,
        item_code=normalized_item_code,
        stock_bucket=normalized_stock_bucket,
        movement_type=None,
        source_event_type=normalized_source_event_type,
        source_event_id=None,
        date_from=date_from,
        date_to=date_to,
    )

    balances: dict[tuple[str, str | None, str], dict[str, object]] = defaultdict(
        lambda: {
            "total_in_qty": 0.0,
            "total_out_qty": 0.0,
            "last_posted_at": None,
        }
    )
    for row in rows:
        item_code = _item_code(row)
        base_uom = _base_uom(row)
        key = (item_code, row.stock_bucket, base_uom)
        qty = _base_qty(row)
        movement_type = _movement_type(row)
        balance = balances[key]
        if movement_type == "IN":
            balance["total_in_qty"] = float(balance["total_in_qty"]) + qty
        elif movement_type == "OUT":
            balance["total_out_qty"] = float(balance["total_out_qty"]) + qty

        posted_at = _posted_at(row)
        current_last_posted_at = balance["last_posted_at"]
        if current_last_posted_at is None or posted_at > current_last_posted_at:
            balance["last_posted_at"] = posted_at

    return [
        StockLedgerBalanceReadResponse(
            item_code=item_code,
            stock_bucket=stock_bucket,
            base_uom=base_uom,
            total_in_qty=float(summary["total_in_qty"]),
            total_out_qty=float(summary["total_out_qty"]),
            net_balance_qty=float(summary["total_in_qty"]) - float(summary["total_out_qty"]),
            last_posted_at=_coerce_datetime(summary["last_posted_at"]),
        )
        for item_code, stock_bucket, base_uom, summary in sorted(
            (
                (item_code, stock_bucket, base_uom, summary)
                for (item_code, stock_bucket, base_uom), summary in balances.items()
            ),
            key=lambda row: (row[0], row[1] or "", row[2]),
        )
    ]


def list_stock_ledger_entries(
    db: Session,
    *,
    org_id: str,
    item_code: str | None = None,
    stock_bucket: str | None = None,
    movement_type: str | None = None,
    source_event_type: str | None = None,
    source_event_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[StockLedgerEntryReadResponse]:
    normalized_item_code = _normalize_optional_text(item_code)
    normalized_stock_bucket = _validate_enum(
        name="stock_bucket",
        value=stock_bucket,
        allowed_values=ALLOWED_STOCK_BUCKETS,
    )
    normalized_movement_type = _validate_enum(
        name="movement_type",
        value=movement_type,
        allowed_values=ALLOWED_MOVEMENT_TYPES,
    )
    normalized_source_event_type = _validate_enum(
        name="source_event_type",
        value=source_event_type,
        allowed_values=ALLOWED_SOURCE_EVENT_TYPES,
    )
    normalized_page = _validate_page(page)
    normalized_page_size = _validate_page_size(page_size)
    _validate_date_range(date_from=date_from, date_to=date_to)
    offset = (normalized_page - 1) * normalized_page_size

    rows = _query_rows(
        db=db,
        org_id=org_id,
        item_code=normalized_item_code,
        stock_bucket=normalized_stock_bucket,
        movement_type=normalized_movement_type,
        source_event_type=normalized_source_event_type,
        source_event_id=source_event_id,
        date_from=date_from,
        date_to=date_to,
    )
    paged_rows = rows[offset: offset + normalized_page_size]
    return [_to_entry_response(row) for row in paged_rows]


def _query_rows(
    *,
    db: Session,
    org_id: str,
    item_code: str | None,
    stock_bucket: str | None,
    movement_type: str | None,
    source_event_type: str | None,
    source_event_id: int | None,
    date_from: date | None,
    date_to: date | None,
) -> list[StockLedger]:
    query = db.query(StockLedger).filter(StockLedger.org_id == org_id)
    if item_code is not None:
        query = query.filter(StockLedger.item_code == item_code)
    if stock_bucket is not None:
        query = query.filter(StockLedger.stock_bucket == stock_bucket)
    if movement_type is not None:
        query = query.filter(StockLedger.movement_type == movement_type)
    if source_event_type is not None:
        query = query.filter(StockLedger.source_event_type == source_event_type)
    if source_event_id is not None:
        query = query.filter(StockLedger.source_event_id == source_event_id)

    rows = query.order_by(StockLedger.posted_at.desc(), StockLedger.occurred_at.desc(), StockLedger.id.desc()).all()
    if date_from is None and date_to is None:
        return rows

    filtered_rows: list[StockLedger] = []
    for row in rows:
        posted_at = _posted_at(row)
        posted_date = posted_at.date()
        if date_from is not None and posted_date < date_from:
            continue
        if date_to is not None and posted_date > date_to:
            continue
        filtered_rows.append(row)
    return filtered_rows


def _to_entry_response(row: StockLedger) -> StockLedgerEntryReadResponse:
    normalized_source_event_type = _normalize_optional_text(row.source_event_type)
    return StockLedgerEntryReadResponse(
        id=int(row.id),
        ledger_no=str(row.ledger_no or ""),
        item_code=_item_code(row),
        stock_bucket=row.stock_bucket,
        movement_type=row.movement_type,
        txn_type=str(row.txn_type or ""),
        txn_qty=_txn_qty(row),
        txn_uom=_txn_uom(row),
        base_qty=_base_qty(row),
        base_uom=_base_uom(row),
        source_event_type=normalized_source_event_type,
        source_event_id=row.source_event_id,
        source_event_line_id=_source_event_line_id(row, normalized_source_event_type),
        work_order_id=row.work_order_id,
        sales_order_id=row.sales_order_id,
        posted_at=_posted_at(row),
        posted_by=str(row.posted_by or ""),
        remark=row.remark,
    )


def _source_event_line_id(row: StockLedger, source_event_type: str | None) -> int | None:
    if source_event_type == "RM_ISSUE":
        return row.source_event_line_id
    if source_event_type in {"FG_RECEIVE", "SHIPMENT"}:
        return None
    return row.source_event_line_id


def _item_code(row: StockLedger) -> str:
    return str(row.item_code or row.item_id or "")


def _movement_type(row: StockLedger) -> str:
    return str(row.movement_type or "").strip().upper()


def _txn_qty(row: StockLedger) -> float:
    if row.txn_qty is not None:
        return float(row.txn_qty)
    qty = float(row.qty or 0)
    return abs(qty)


def _txn_uom(row: StockLedger) -> str:
    return str(row.txn_uom or row.uom or "")


def _base_qty(row: StockLedger) -> float:
    if row.base_qty is not None:
        return float(row.base_qty)
    qty = float(row.qty or 0)
    return abs(qty)


def _base_uom(row: StockLedger) -> str:
    return str(row.base_uom or row.uom or "")


def _posted_at(row: StockLedger) -> datetime:
    posted_at = row.posted_at or row.occurred_at
    if posted_at is None:
        return datetime.combine(date.min, time.min)
    return posted_at


def _coerce_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.combine(date.min, time.min)


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _validate_enum(*, name: str, value: str | None, allowed_values: set[str]) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    upper_value = normalized.upper()
    if upper_value not in allowed_values:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {name}: expected one of {', '.join(sorted(allowed_values))}",
        )
    return upper_value


def _validate_date_range(*, date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="Invalid date range: date_from must be on or before date_to")


def _validate_page(page: int) -> int:
    if page < 1:
        raise HTTPException(status_code=422, detail="Invalid page: must be >= 1")
    return page


def _validate_page_size(page_size: int) -> int:
    if page_size < 1 or page_size > 200:
        raise HTTPException(status_code=422, detail="Invalid page_size: must be between 1 and 200")
    return page_size
