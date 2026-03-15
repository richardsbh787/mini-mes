from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


WorkOrderRoutingExecutionStepStatus = Literal["PENDING", "ACTIVE", "DONE"]


class WorkOrderRoutingExecutionReadStep(BaseModel):
    seq_no: int
    step_code: str
    step_name: str
    department: str | None
    is_required: bool
    step_status: WorkOrderRoutingExecutionStepStatus


class WorkOrderRoutingExecutionReadResponse(BaseModel):
    work_order_id: int
    work_order_no: str
    routing_snapshot_id: int
    routing_code: str
    routing_name: str
    has_active_step: bool
    is_routing_completed: bool
    active_step: WorkOrderRoutingExecutionReadStep | None
    steps: list[WorkOrderRoutingExecutionReadStep]
