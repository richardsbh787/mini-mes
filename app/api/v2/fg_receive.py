from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.stock_ledger_fg_receive import FgReceiveLedgerPostRequest, StockLedgerFgReceiveResponse
from app.schemas.work_order_fg_receive import WorkOrderFgReceiveCreateRequest, WorkOrderFgReceiveResponse
from app.services.work_order_fg_receive_ledger import get_fg_receive_stock_ledger, post_fg_receive_stock_ledger
from app.services.work_order_fg_receive import (
    create_work_order_fg_receive,
    get_work_order_fg_receive,
    list_work_order_fg_receipts,
)
from database import get_db


router = APIRouter(tags=["v2-work-order-fg-receive"])


@router.post("/work-orders/{work_order_id}/fg-receipts", response_model=WorkOrderFgReceiveResponse)
def work_order_fg_receive_create(
    work_order_id: int,
    payload: WorkOrderFgReceiveCreateRequest,
    db: Session = Depends(get_db),
):
    return create_work_order_fg_receive(db=db, work_order_id=work_order_id, payload=payload)


@router.get("/work-orders/{work_order_id}/fg-receipts", response_model=list[WorkOrderFgReceiveResponse])
def work_order_fg_receive_list(
    work_order_id: int,
    db: Session = Depends(get_db),
):
    return list_work_order_fg_receipts(db=db, work_order_id=work_order_id)


@router.get("/fg-receipts/{fg_receive_id}", response_model=WorkOrderFgReceiveResponse)
def work_order_fg_receive_detail(
    fg_receive_id: int,
    db: Session = Depends(get_db),
):
    return get_work_order_fg_receive(db=db, fg_receive_id=fg_receive_id)


@router.post("/fg-receipts/{fg_receive_id}/post-ledger", response_model=StockLedgerFgReceiveResponse)
def fg_receive_stock_ledger_post(
    fg_receive_id: int,
    payload: FgReceiveLedgerPostRequest,
    db: Session = Depends(get_db),
):
    return post_fg_receive_stock_ledger(db=db, fg_receive_id=fg_receive_id, payload=payload)


@router.get("/stock-ledger/fg-receipts/{fg_receive_id}", response_model=StockLedgerFgReceiveResponse)
def fg_receive_stock_ledger_detail(
    fg_receive_id: int,
    db: Session = Depends(get_db),
):
    return get_fg_receive_stock_ledger(db=db, fg_receive_id=fg_receive_id)
