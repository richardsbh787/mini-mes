from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FgReceiveLedgerPostRequest(BaseModel):
    posted_by: str
    remark: str | None = None


class StockLedgerFgReceiveResponse(BaseModel):
    id: int
    ledger_no: str
    source_event_type: str
    source_event_id: int
    work_order_id: int
    sales_order_id: int | None
    item_code: str
    movement_type: str
    stock_bucket: str
    txn_qty: float
    txn_uom: str
    base_qty: float
    base_uom: str
    posted_at: datetime
    posted_by: str
    remark: str | None
