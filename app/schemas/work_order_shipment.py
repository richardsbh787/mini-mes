from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WorkOrderShipmentCreateRequest(BaseModel):
    fg_receive_id: int
    txn_qty: float
    txn_uom: str
    shipment_ref: str
    shipment_remark: str | None = None
    shipped_by: str


class WorkOrderShipmentResponse(BaseModel):
    id: int
    shipment_no: str
    work_order_id: int
    sales_order_id: int
    fg_receive_id: int
    txn_qty: float
    txn_uom: str
    shipment_ref: str
    shipment_remark: str | None
    shipment_status: str
    shipped_at: datetime
    shipped_by: str
