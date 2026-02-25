from pydantic import BaseModel, Field
from typing import Any, List, Optional

class RoutingStep(BaseModel):
    seq: int = Field(..., ge=1)
    stage: str = Field(..., min_length=1)     # 中性词：stage（客户可理解成 dept/section）
    process: str = Field(..., min_length=1)   # 工序名/站点名

    # 预留：以后你要“某工序只能在某些线做”再启用
    allowed_lines: Optional[List[str]] = None

class ModelRoutingUpsertIn(BaseModel):
    org_id: str
    model_code: str
    steps: List[RoutingStep]
    version: int = 1
    is_active: bool = True

class ModelRoutingOut(BaseModel):
    id: str
    org_id: str
    model_code: str
    version: int
    is_active: bool
    steps: Any
    created_at: str
    updated_at: str