from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RoutingHeaderCreate(BaseModel):
    """Minimal process-definition container for a target item."""

    item_code: str = Field(..., min_length=1)
    routing_code: str = Field(..., min_length=1)
    routing_name: str = Field(..., min_length=1)
    status: str = Field(..., min_length=1)


class RoutingStepCreate(BaseModel):
    """Sequential process-definition node under a routing."""

    seq_no: int = Field(..., gt=0)
    step_code: str = Field(..., min_length=1)
    step_name: str = Field(..., min_length=1)
    department: str | None = None
    is_required: bool


class RoutingStepOut(RoutingStepCreate):
    id: int
    routing_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoutingHeaderOut(RoutingHeaderCreate):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RoutingHeaderDetail(RoutingHeaderOut):
    steps: list[RoutingStepOut] = []
