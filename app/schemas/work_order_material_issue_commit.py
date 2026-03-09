from datetime import datetime

from pydantic import BaseModel, Field


class WorkOrderMaterialIssueCommitRequest(BaseModel):
    snapshot_id: int = Field(..., gt=0)
    org_id: str = Field(..., min_length=1)
    location_id: str = Field(..., min_length=1)
    issued_by: str = Field(..., min_length=1)


class MaterialIssueLedgerRow(BaseModel):
    item_code: str
    qty: float
    uom: str
    txn_type: str


class WorkOrderMaterialIssueCommitResponse(BaseModel):
    snapshot_id: int
    work_order_no: str
    status: str
    issue_status: str
    issued_by: str | None = None
    issued_at: datetime | None = None
    ledger_rows: list[MaterialIssueLedgerRow]
