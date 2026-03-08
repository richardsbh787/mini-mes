from typing import Optional

from pydantic import BaseModel, Field


class TreeExplosionRequest(BaseModel):
    parent_system_item_code: str = Field(..., min_length=1)
    required_qty: float = Field(..., gt=0)
    version_id: Optional[int] = None


class TreeNode(BaseModel):
    item_code: str
    item_name: Optional[str] = None
    required_qty: float
    uom: Optional[str] = None
    level: int
    path: list[str]
    is_phantom: bool
    is_leaf: bool
    children: list["TreeNode"] = Field(default_factory=list)


class TreeExplosionResponse(BaseModel):
    root_item_code: str
    version_id: int
    tree: TreeNode
