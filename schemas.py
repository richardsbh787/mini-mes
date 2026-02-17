from pydantic import BaseModel
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


class WorkOrderResponse(BaseModel):
    id: int
    work_order_no: str
    sales_order_id: int
    product_id: int
    production_line_id: int

    planned_hours: float
    actual_hours: float
    remaining_hours: float

    priority: str
    promise_date: date
    status: WorkOrderStatus

    is_material_ready: bool
    material_ready_date: Optional[date]

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




