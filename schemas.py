from pydantic import BaseModel, Field, field_validator
from datetime import date, datetime
from typing import Optional
from enum import Enum


# ==========================================================
# ENUM
# ==========================================================

class WorkOrderStatus(str, Enum):
    OPEN = "OPEN"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    BLOCKED_MATERIAL = "BLOCKED_MATERIAL"
    DONE = "DONE"


# ==========================================================
# Product
# ==========================================================

class ProductCreate(BaseModel):
    model_no: str
    model_description: Optional[str] = None
    product_family: Optional[str] = None
    product_family_power: Optional[str] = None


class ProductResponse(ProductCreate):
    id: int

    class Config:
        from_attributes = True


# ==========================================================
# Sales Order
# ==========================================================

class SalesOrderCreate(BaseModel):
    order_no: str
    customer_name: str
    order_date: date
    shipment_date: Optional[date] = None


class SalesOrderResponse(SalesOrderCreate):
    id: int
    status: str    

    class Config:
        from_attributes = True


# ==========================================================
# Production Line
# ==========================================================

class ProductionLineCreate(BaseModel):
    line_name: str
    working_hours_per_day: float
    efficiency_rate: float


class ProductionLineResponse(ProductionLineCreate):
    id: int
    is_active: bool

    class Config:
        from_attributes = True


# ==========================================================
# Work Order
# ==========================================================

class WorkOrderCreate(BaseModel):
    work_order_no: str
    sales_order_id: int
    product_id: int
    production_line_id: int
    routing_id: Optional[int] = None
    planned_hours: float
    priority: str
    promise_date: date
    is_material_ready: bool = False
    material_ready_date: Optional[date] = None


class WorkOrderUpdate(BaseModel):
    planned_hours: Optional[float] = None
    remaining_hours: Optional[float] = None
    priority: Optional[str] = None
    promise_date: Optional[date] = None
    status: Optional[WorkOrderStatus] = None


class WorkOrderRoutingStepDefinition(BaseModel):
    seq_no: int
    step_code: str
    step_name: str
    department: Optional[str]
    is_required: bool

    class Config:
        from_attributes = True


class WorkOrderRoutingDefinition(BaseModel):
    routing_id: int
    routing_code: str
    routing_name: str
    routing_status: str
    steps: list[WorkOrderRoutingStepDefinition] = []

    class Config:
        from_attributes = True


class WorkOrderRoutingSnapshotStepRead(BaseModel):
    seq_no: int
    step_code: str
    step_name: str
    department: Optional[str]
    is_required: bool

    class Config:
        from_attributes = True


class WorkOrderRoutingSnapshotRead(BaseModel):
    snapshot_id: int
    source_routing_id: int
    routing_code: str
    routing_name: str
    steps: list[WorkOrderRoutingSnapshotStepRead] = []

    class Config:
        from_attributes = True


class WorkOrderResponse(BaseModel):
    id: int
    work_order_no: str
    sales_order_id: int
    product_id: int
    production_line_id: int
    routing_id: Optional[int]

    planned_hours: float
    actual_hours: float
    remaining_hours: float

    priority: str
    promise_date: date
    status: WorkOrderStatus

    is_material_ready: bool
    material_ready_date: Optional[date]
    routing_definition: Optional[WorkOrderRoutingDefinition] = None
    routing_snapshot: Optional[WorkOrderRoutingSnapshotRead] = None

    created_datetime: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ==========================================================
# Production Log
# ==========================================================

class ProductionLogCreate(BaseModel):
    production_line_id: int
    work_order_id: int
    produced_hours: float
    scrap_hours: float = 0
    rework_hours: float = 0
    rework_consumes_material: bool = False   # ✅ 加这一行
    log_date: date


class ProductionLogResponse(ProductionLogCreate):
    id: int

    class Config:
        from_attributes = True


# ==========================================================
# Production Event Schema
# ==========================================================

class ProductionEventCreate(BaseModel):
    production_line_id: int
    event_type: str
    impact_hours: float
    description: Optional[str] = None
    event_date: date


class ProductionEventResponse(ProductionEventCreate):
    id: int
    is_resolved: bool
    resolved_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True



# ==========================================================
# Inventory Schema
# ==========================================================

class InventoryCreate(BaseModel):
    product_id: int
    quantity_on_hand: float


class InventoryResponse(BaseModel):
    id: int
    product_id: int
    quantity_on_hand: float
    last_updated: datetime

    class Config:
        from_attributes = True


# ==========================================================
# Raw Material Schema
# ==========================================================

class RawMaterialCreate(BaseModel):
    material_code: str
    material_name: str
    unit: str
    conversion_type: str = "STANDARD"
    standard_conversion_ratio: float = Field(default=1.0, gt=0)

    @field_validator("conversion_type")
    @classmethod
    def validate_conversion_type(cls, value: str) -> str:
        normalized = str(value or "").strip().upper()
        if normalized not in {"STANDARD", "LOT_ACTUAL"}:
            raise ValueError("conversion_type must be STANDARD or LOT_ACTUAL")
        return normalized


class RawMaterialResponse(RawMaterialCreate):
    id: int

    class Config:
        from_attributes = True


# ==========================================================
# BOM Schema
# ==========================================================

class BOMCreate(BaseModel):
    product_id: int
    raw_material_id: int
    quantity_required: float


class BOMResponse(BOMCreate):
    id: int

    class Config:
        from_attributes = True






