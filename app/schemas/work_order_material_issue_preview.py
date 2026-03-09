from pydantic import BaseModel, Field


class WorkOrderMaterialIssuePreviewRequest(BaseModel):
    snapshot_id: int = Field(..., gt=0)


class WorkOrderMaterialIssueLine(BaseModel):
    item_code: str
    item_name: str | None = None
    required_qty: float
    uom: str


class WorkOrderMaterialIssuePreviewResponse(BaseModel):
    snapshot_id: int
    work_order_no: str
    parent_system_item_code: str
    work_order_qty: float
    bom_version_id: int
    status: str
    issue_lines: list[WorkOrderMaterialIssueLine]
