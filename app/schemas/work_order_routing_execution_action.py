from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


WorkOrderRoutingExecutionPersistedStatus = Literal["ACTIVE", "DONE"]


class WorkOrderRoutingExecutionActionRequest(BaseModel):
    work_order_id: int = Field(..., gt=0)
    step_code: str | None = Field(default=None, min_length=1)
    seq_no: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_explicit_locator(self) -> "WorkOrderRoutingExecutionActionRequest":
        if self.step_code is None and self.seq_no is None:
            raise ValueError("step_code or seq_no is required")
        return self


class WorkOrderRoutingExecutionStartActionRequest(WorkOrderRoutingExecutionActionRequest):
    started_by: str = Field(..., min_length=1)


class WorkOrderRoutingExecutionReleaseActionRequest(WorkOrderRoutingExecutionActionRequest):
    completed_by: str = Field(..., min_length=1)


class WorkOrderRoutingExecutionActionStep(BaseModel):
    seq_no: int
    step_code: str
    step_name: str
    department: str | None
    is_required: bool


class WorkOrderRoutingExecutionActionActiveStateSummary(BaseModel):
    has_active_step: bool
    active_step: WorkOrderRoutingExecutionActionStep | None


class WorkOrderRoutingExecutionActionResponse(BaseModel):
    work_order_id: int
    routing_snapshot_id: int
    affected_step: WorkOrderRoutingExecutionActionStep
    active_state: WorkOrderRoutingExecutionActionActiveStateSummary
    execution_status: WorkOrderRoutingExecutionPersistedStatus
