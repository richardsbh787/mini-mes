from datetime import datetime

from pydantic import BaseModel, Field


class WorkOrderBOMReleaseRequest(BaseModel):
    snapshot_id: int = Field(..., gt=0)
    released_by: str = Field(..., min_length=1)


class WorkOrderBOMReleaseResponse(BaseModel):
    snapshot_id: int
    work_order_no: str
    status: str
    released_by: str | None = None
    released_at: datetime | None = None
