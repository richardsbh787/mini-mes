from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.schemas.stock_ledger_read import (
    StockLedgerBalanceReadResponse,
    StockLedgerEntryReadResponse,
)
from models import StockLedger


def list_stock_ledger_balance(
    db: Session,
    *,
    org_id: str,
    source_event_type: str | None = None,
) -> list[StockLedgerBalanceReadResponse]:
    rows = _base_query(db=db, org_id=org_id, source_event_type=source_event_type).order_by(
        StockLedger.id.asc()
    ).all()

    balances: dict[tuple[str, str | None, str], float] = defaultdict(float)
    for row in rows:
        item_code = _item_code(row)
        base_uom = _base_uom(row)
        key = (item_code, row.stock_bucket, base_uom)
        qty = _base_qty(row)
        balances[key] += qty if _movement_type(row) == "IN" else 0 - qty

    return [
        StockLedgerBalanceReadResponse(
            item_code=item_code,
            stock_bucket=stock_bucket,
            base_uom=base_uom,
            net_base_qty=net_base_qty,
        )
        for item_code, stock_bucket, base_uom, net_base_qty in sorted(
            (
                (item_code, stock_bucket, base_uom, net_base_qty)
                for (item_code, stock_bucket, base_uom), net_base_qty in balances.items()
            ),
            key=lambda row: (row[0], row[1] or "", row[2]),
        )
    ]


def list_stock_ledger_entries(
    db: Session,
    *,
    org_id: str,
    source_event_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[StockLedgerEntryReadResponse]:
    normalized_page = max(page, 1)
    normalized_page_size = min(max(page_size, 1), 200)
    offset = (normalized_page - 1) * normalized_page_size

    rows = (
        _base_query(db=db, org_id=org_id, source_event_type=source_event_type)
        .order_by(StockLedger.posted_at.desc(), StockLedger.occurred_at.desc(), StockLedger.id.desc())
        .offset(offset)
        .limit(normalized_page_size)
        .all()
    )
    return [_to_entry_response(row) for row in rows]


def _base_query(
    *,
    db: Session,
    org_id: str,
    source_event_type: str | None,
):
    query = db.query(StockLedger).filter(StockLedger.org_id == org_id)
    normalized_source_event_type = _normalize_optional_text(source_event_type)
    if normalized_source_event_type is not None:
        query = query.filter(StockLedger.source_event_type == normalized_source_event_type)
    return query


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
        posted_at=row.posted_at or row.occurred_at,
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


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None
