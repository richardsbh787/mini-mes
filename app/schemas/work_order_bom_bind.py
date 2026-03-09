from pydantic import BaseModel, Field

from app.schemas.bom_explosion import FlatExplosionLine
from app.schemas.bom_tree_explosion import TreeNode


class WorkOrderBOMBindRequest(BaseModel):
    work_order_no: str = Field(..., min_length=1)
    parent_system_item_code: str = Field(..., min_length=1)
    work_order_qty: float = Field(..., gt=0)
    version_id: int | None = None
    created_by: str | None = None


class WorkOrderBOMBindResponse(BaseModel):
    snapshot_id: int
    work_order_no: str
    parent_system_item_code: str
    work_order_qty: float
    version_id: int
    flat_materials: list[FlatExplosionLine]
    tree: TreeNode
