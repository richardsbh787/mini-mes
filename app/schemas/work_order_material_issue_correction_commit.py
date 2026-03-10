from datetime import datetime

from pydantic import BaseModel, Field, field_validator


ALLOWED_CORRECTION_REASON_CODES = {
    "WRONG_ITEM",
    "WRONG_QTY",
    "DUPLICATE_ISSUE",
    "RETURN_TO_STOCK",
    "OTHER",
}


class WorkOrderMaterialIssueCorrectionCommitRequest(BaseModel):
    original_issue_event_id: int = Field(..., gt=0)
    reason_code: str = Field(..., min_length=1)
    reason_note: str | None = None
    corrected_by: str = Field(..., min_length=1)

    @field_validator("reason_code")
    @classmethod
    def normalize_reason_code(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("reason_note")
    @classmethod
    def normalize_reason_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class MaterialIssueCorrectionLedgerRow(BaseModel):
    item_code: str
    qty: float
    uom: str
    txn_type: str


class WorkOrderMaterialIssueCorrectionCommitResponse(BaseModel):
    correction_event_id: int
    original_issue_event_id: int
    snapshot_id: int
    work_order_no: str
    corrected_by: str
    corrected_at: datetime
    ledger_rows: list[MaterialIssueCorrectionLedgerRow]
