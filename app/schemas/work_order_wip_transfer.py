from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WorkOrderWipTransferCreateRequest(BaseModel):
    from_step_no: int
    to_step_no: int
    handling_unit_type: str
    handling_unit_label: str | None = None
    txn_qty: float
    txn_uom: str
    created_by: str


class WorkOrderWipTransferQcDecisionRequest(BaseModel):
    qc_decision: str
    qc_decided_by: str
    qc_remark: str | None = None


class WorkOrderWipTransferResponse(BaseModel):
    id: int
    transfer_no: str
    work_order_id: int
    routing_snapshot_id: int
    from_step_no: int
    to_step_no: int
    handling_unit_type: str
    handling_unit_label: str | None
    txn_qty: float
    txn_uom: str
    base_qty: float
    base_uom: str
    transfer_status: str
    qc_decision: str | None
    qc_decided_at: datetime | None
    qc_decided_by: str | None
    qc_remark: str | None
    is_available_for_next_step: bool
    created_at: datetime
    created_by: str
