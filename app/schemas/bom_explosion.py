from typing import Optional

from pydantic import BaseModel, Field


class FlatExplosionRequest(BaseModel):
    parent_system_item_code: str = Field(..., min_length=1)
    required_qty: float = Field(..., gt=0)
    version_id: Optional[int] = None


class FlatExplosionLine(BaseModel):
    item_code: str
    item_name: Optional[str] = None
    total_qty: float
    uom: str
