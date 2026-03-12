from pydantic import BaseModel, Field


class WorkOrderRoutingBindRequest(BaseModel):
    work_order_id: int = Field(..., gt=0)
    routing_id: int = Field(..., gt=0)
