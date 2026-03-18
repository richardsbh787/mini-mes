from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.stock_ledger_read import (
    StockLedgerBalanceReadResponse,
    StockLedgerEntryReadResponse,
)
from app.services.stock_ledger_read import list_stock_ledger_balance, list_stock_ledger_entries
from database import get_db


router = APIRouter(prefix="/v2/stock-ledger", tags=["v2-stock-ledger-read"])

StockBucket = Literal["RAW_MATERIAL", "FINISHED_GOODS"]
MovementType = Literal["IN", "OUT"]
SourceEventType = Literal["FG_RECEIVE", "SHIPMENT", "RM_ISSUE"]


@router.get("/balance", response_model=list[StockLedgerBalanceReadResponse])
def stock_ledger_balance(
    org_id: str,
    item_code: str | None = None,
    stock_bucket: StockBucket | None = None,
    source_event_type: SourceEventType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
):
    return list_stock_ledger_balance(
        db=db,
        org_id=org_id,
        item_code=item_code,
        stock_bucket=stock_bucket,
        source_event_type=source_event_type,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/entries", response_model=list[StockLedgerEntryReadResponse])
def stock_ledger_entries(
    org_id: str,
    item_code: str | None = None,
    stock_bucket: StockBucket | None = None,
    movement_type: MovementType | None = None,
    source_event_type: SourceEventType | None = None,
    source_event_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    return list_stock_ledger_entries(
        db=db,
        org_id=org_id,
        item_code=item_code,
        stock_bucket=stock_bucket,
        movement_type=movement_type,
        source_event_type=source_event_type,
        source_event_id=source_event_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
