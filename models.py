from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


# ==========================
# Product
# ==========================

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    model_no = Column(String, nullable=False)
    model_description = Column(String)
    product_family = Column(String)
    product_family_power = Column(String)


# ==========================
# Sales Order
# ==========================

class SalesOrder(Base):
    __tablename__ = "sales_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String, unique=True, nullable=False)
    customer_name = Column(String, nullable=False)
    order_date = Column(Date, nullable=False)
    shipment_date = Column(Date)

# ==========================
# Production Line (小时模型)
# ==========================

class ProductionLine(Base):
    __tablename__ = "production_lines"

    id = Column(Integer, primary_key=True, index=True)

    # ✅ 关键修改：名称唯一
    line_name = Column(String, nullable=False, unique=True)

    working_hours_per_day = Column(Float, nullable=False)
    efficiency_rate = Column(Float, nullable=False, default=1.0)

    is_active = Column(Boolean, nullable=False, default=True)



# ==============================
# Work Order (小时驱动)
# ==============================

class WorkOrder(Base):
    __tablename__ = "work_orders"

    # ==========================
    # Primary Key
    # ==========================
    id = Column(Integer, primary_key=True, index=True)
    work_order_no = Column(String, unique=True, nullable=False)

    # ==========================
    # Foreign Keys
    # ==========================
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    production_line_id = Column(Integer, ForeignKey("production_lines.id"), nullable=False)

    # ==========================
    # Hours Control
    # ==========================
    planned_hours = Column(Float, nullable=False)
    actual_hours = Column(Float, nullable=False, default=0)
    remaining_hours = Column(Float, nullable=False)

    # ==========================
    # Priority & Promise
    # ==========================
    priority = Column(String, nullable=False, default="NORMAL")
    promise_date = Column(Date, nullable=False)

    # ==========================
    # Material Gate
    # ==========================
    is_material_ready = Column(Boolean, nullable=False, default=False)
    material_ready_date = Column(Date, nullable=True)

    # ==========================
    # Status Machine
    # ==========================
    status = Column(String, nullable=False, default="OPEN")

    # ==========================
    # Execution Timeline
    # ==========================
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # ==========================
    # System
    # ==========================
    created_datetime = Column(DateTime, nullable=False, default=datetime.utcnow)

    # ==========================
    # Relationships
    # ==========================
    sales_order = relationship("SalesOrder")
    product = relationship("Product")
    production_line = relationship("ProductionLine")


# ==========================================================
# Production Log（每日生产记录）
# ==========================================================

class ProductionLog(Base):
    __tablename__ = "production_logs"

    id = Column(Integer, primary_key=True, index=True)

    production_line_id = Column(Integer, ForeignKey("production_lines.id"))
    work_order_id = Column(Integer, ForeignKey("work_orders.id"))

    produced_hours = Column(Float, default=0)   # 实际完成工时
    scrap_hours = Column(Float, default=0)      # 报废损耗
    rework_hours = Column(Float, default=0)     # 返工工时

    log_date = Column(Date, nullable=False)
    created_datetime = Column(DateTime, default=datetime.utcnow)

    production_line = relationship("ProductionLine")
    work_order = relationship("WorkOrder")


# ==========================================================
# Production Event（异常事件）
# ==========================================================

class ProductionEvent(Base):
    __tablename__ = "production_events"

    # ==========================
    # Primary Key
    # ==========================
    id = Column(Integer, primary_key=True, index=True)

    # ==========================
    # Foreign Key
    # ==========================
    production_line_id = Column(
        Integer,
        ForeignKey("production_lines.id"),
        nullable=False
    )

    # ==========================
    # Event Info
    # ==========================
    event_type = Column(String, nullable=False)
    impact_hours = Column(Float, nullable=False)
    description = Column(String, nullable=True)
    event_date = Column(Date, nullable=False)

    # ==========================
    # Resolution Control
    # ==========================
    is_resolved = Column(Boolean, nullable=False, default=False)
    resolved_at = Column(DateTime, nullable=True)

    # ==========================
    # System
    # ==========================
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # ==========================
    # Relationship
    # ==========================
    production_line = relationship("ProductionLine")


# ==========================================================
# Inventory（成品库存）
# ==========================================================

class Inventory(Base):
    __tablename__ = "inventories"

    id = Column(Integer, primary_key=True, index=True)

    product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=False,
        unique=True  # 每个产品一条库存记录
    )

    quantity_on_hand = Column(Float, nullable=False, default=0)

    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)

    product = relationship("Product")



