from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class StockLedgerBalanceReadResponse(BaseModel):
    item_code: str
    stock_bucket: str | None
    base_uom: str
    net_base_qty: float


class StockLedgerEntryReadResponse(BaseModel):
    id: int
    ledger_no: str
    item_code: str
    stock_bucket: str | None
    movement_type: str | None
    txn_type: str
    txn_qty: float
    txn_uom: str
    base_qty: float
    base_uom: str
    source_event_type: str | None
    source_event_id: int | None
    source_event_line_id: int | None
    work_order_id: int | None
    sales_order_id: int | None
    posted_at: datetime
    posted_by: str
    remark: str | None
