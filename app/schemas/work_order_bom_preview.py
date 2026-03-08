from pydantic import BaseModel, Field

from app.schemas.bom_explosion import FlatExplosionLine
from app.schemas.bom_tree_explosion import TreeNode


class WorkOrderBOMPreviewRequest(BaseModel):
    parent_system_item_code: str = Field(..., min_length=1)
    work_order_qty: float = Field(..., gt=0)
    version_id: int | None = None


class WorkOrderBOMPreviewResponse(BaseModel):
    parent_system_item_code: str
    work_order_qty: float
    version_id: int
    flat_materials: list[FlatExplosionLine]
    tree: TreeNode
