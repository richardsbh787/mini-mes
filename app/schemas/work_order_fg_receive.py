from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WorkOrderFgReceiveCreateRequest(BaseModel):
    wip_transfer_id: int
    fg_handling_unit_type: str
    fg_handling_unit_label: str | None = None
    txn_qty: float
    txn_uom: str
    received_by: str
    remark: str | None = None


class WorkOrderFgReceiveResponse(BaseModel):
    id: int
    fg_receive_no: str
    work_order_id: int
    wip_transfer_id: int
    routing_snapshot_id: int
    fg_handling_unit_type: str
    fg_handling_unit_label: str | None
    txn_qty: float
    txn_uom: str
    receive_status: str
    received_at: datetime
    received_by: str
    remark: str | None
