from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.stock_ledger_read import (
    StockLedgerBalanceReadResponse,
    StockLedgerEntryReadResponse,
)
from app.services.stock_ledger_read import list_stock_ledger_balance, list_stock_ledger_entries
from database import get_db


router = APIRouter(prefix="/v2/stock-ledger", tags=["v2-stock-ledger-read"])


@router.get("/balance", response_model=list[StockLedgerBalanceReadResponse])
def stock_ledger_balance(
    org_id: str,
    source_event_type: str | None = None,
    db: Session = Depends(get_db),
):
    return list_stock_ledger_balance(
        db=db,
        org_id=org_id,
        source_event_type=source_event_type,
    )


@router.get("/entries", response_model=list[StockLedgerEntryReadResponse])
def stock_ledger_entries(
    org_id: str,
    source_event_type: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    return list_stock_ledger_entries(
        db=db,
        org_id=org_id,
        source_event_type=source_event_type,
        page=page,
        page_size=page_size,
    )
