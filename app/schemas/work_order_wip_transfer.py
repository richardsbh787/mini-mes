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
    created_at: datetime
    created_by: str
