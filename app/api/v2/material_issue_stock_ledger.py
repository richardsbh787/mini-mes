from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.stock_ledger_rm_issue import RmIssueLedgerPostRequest, StockLedgerRmIssueResponse
from app.services.work_order_material_issue_ledger import list_rm_issue_stock_ledger, post_rm_issue_stock_ledger
from database import get_db


router = APIRouter(tags=["v2-work-order-material-issue-ledger"])


@router.post("/rm-issues/{issue_event_id}/post-ledger", response_model=list[StockLedgerRmIssueResponse])
def rm_issue_stock_ledger_post(
    issue_event_id: int,
    payload: RmIssueLedgerPostRequest,
    db: Session = Depends(get_db),
):
    return post_rm_issue_stock_ledger(db=db, issue_event_id=issue_event_id, payload=payload)


@router.get("/stock-ledger/rm-issues/{issue_event_id}", response_model=list[StockLedgerRmIssueResponse])
def rm_issue_stock_ledger_list(
    issue_event_id: int,
    db: Session = Depends(get_db),
):
    return list_rm_issue_stock_ledger(db=db, issue_event_id=issue_event_id)
