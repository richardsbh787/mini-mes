from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class BOMHeaderCreate(BaseModel):
    parent_system_item_code: str
    bom_type: str
    status: str
    created_by: str


class BOMHeaderOut(BOMHeaderCreate):
    bom_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BOMVersionCreate(BaseModel):
    bom_revision: str
    status: str
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    remarks: Optional[str] = None
    created_by: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    source_version_id: Optional[int] = None
    change_trigger: Optional[str] = None


class BOMVersionOut(BOMVersionCreate):
    version_id: int
    bom_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BOMLineCreate(BaseModel):
    sequence: int = Field(..., gt=0)
    component_system_item_code: str
    qty_per: float = Field(..., gt=0)
    uom: str = Field(..., min_length=1)
    scrap_rate: float = Field(0, ge=0, lt=1)
    phantom_flag: bool = False
    alt_group: Optional[int] = None
    alt_priority: Optional[int] = None
    operation_id: Optional[str] = None
    notes: Optional[str] = None


class BOMLineOut(BOMLineCreate):
    bom_line_id: int
    version_id: int

    class Config:
        from_attributes = True


class BOMVersionDetail(BOMVersionOut):
    lines: list[BOMLineOut] = []


class BOMHeaderDetail(BOMHeaderOut):
    versions: list[BOMVersionDetail] = []
