from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey, UniqueConstraint
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
    status = Column(String, nullable=False, default="OPEN")   # ✅ 新增


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
    routing_id = Column(Integer, ForeignKey("routing_header.id"), nullable=True)

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
    routing = relationship("RoutingHeader")
    routing_snapshot = relationship("WorkOrderRoutingSnapshot", back_populates="work_order", uselist=False)


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
    rework_consumes_material = Column(Boolean, nullable=False, default=False)

    

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


# ==========================================================
# BOM (Bill of Material)
# ==========================================================

class BOM(Base):
    __tablename__ = "boms"

    id = Column(Integer, primary_key=True, index=True)

    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    raw_material_id = Column(Integer, ForeignKey("raw_materials.id"), nullable=False)

    quantity_required = Column(Float, nullable=False)
    scrap_rate = Column(Float, nullable=False, default=0)

    product = relationship("Product")
    raw_material = relationship("RawMaterial")


# ==========================================================
# Raw Material Inventory
# ==========================================================

class RawMaterialInventory(Base):
    __tablename__ = "raw_material_inventories"

    id = Column(Integer, primary_key=True, index=True)

    raw_material_id = Column(
        Integer,
        ForeignKey("raw_materials.id"),
        nullable=False,
        unique=True
    )

    quantity_on_hand = Column(Float, nullable=False, default=0)

    raw_material = relationship("RawMaterial")



# ==========================================================
# Raw Material
# ==========================================================

class RawMaterial(Base):
    __tablename__ = "raw_materials"

    id = Column(Integer, primary_key=True, index=True)
    material_code = Column(String, unique=True, nullable=False)
    material_name = Column(String, nullable=False)
    unit = Column(String, nullable=False)


# ==========================================================
# Material Transaction（自动扣料记录）
# ==========================================================

class MaterialTransaction(Base):
    __tablename__ = "material_transactions"

    id = Column(Integer, primary_key=True, index=True)

    raw_material_id = Column(
        Integer,
        ForeignKey("raw_materials.id"),
        nullable=False
    )

    work_order_id = Column(
        Integer,
        ForeignKey("work_orders.id"),
        nullable=False
    )

    quantity = Column(Float, nullable=False)

    transaction_type = Column(String, nullable=False, default="CONSUME")

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    raw_material = relationship("RawMaterial")
    work_order = relationship("WorkOrder")


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id = Column(Integer, primary_key=True, index=True)

    item_type = Column(String, nullable=False)
    # RAW 或 FINISHED

    item_id = Column(Integer, nullable=False)

    transaction_type = Column(String, nullable=False)
    # RECEIVE / CONSUME / SHIP / RETURN / ADJUST

    quantity = Column(Float, nullable=False)

    reference_id = Column(Integer, nullable=True)
    # 工单ID 或 销售订单ID

    created_at = Column(DateTime, default=datetime.utcnow)


class StockLedger(Base):
    __tablename__ = "stock_ledger"

    id = Column(Integer, primary_key=True, index=True)

    org_id = Column(String, nullable=False, index=True)
    item_id = Column(String, nullable=False, index=True)
    location_id = Column(String, nullable=True, index=True)

    txn_type = Column(String, nullable=False)  # ISSUE / RECEIPT / ADJ_701 / ADJ_702
    qty = Column(Float, nullable=False)
    uom = Column(String, nullable=False, default="PCS")

    ref_type = Column(String, nullable=True)
    ref_id = Column(String, nullable=True)
    note = Column(String, nullable=True)
    issue_event_id = Column(Integer, nullable=True, index=True)
    correction_event_id = Column(Integer, nullable=True, index=True)
    snapshot_id = Column(Integer, nullable=True, index=True)
    work_order_no = Column(String, nullable=True, index=True)

    occurred_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# ==========================================================
# Multi-Level BOM (Step 1: Structure Only)
# ==========================================================

class BOMHeader(Base):
    __tablename__ = "bom_header"

    bom_id = Column(Integer, primary_key=True, index=True)
    parent_system_item_code = Column(String, nullable=False, index=True)
    bom_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(String, nullable=False)

    versions = relationship("BOMVersion", back_populates="bom_header")


class BOMVersion(Base):
    __tablename__ = "bom_version"

    version_id = Column(Integer, primary_key=True, index=True)
    bom_id = Column(Integer, ForeignKey("bom_header.bom_id"), nullable=False, index=True)
    bom_revision = Column(String, nullable=False)
    status = Column(String, nullable=False)
    effective_from = Column(Date, nullable=True)
    effective_to = Column(Date, nullable=True)
    remarks = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(String, nullable=False)
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    source_version_id = Column(Integer, ForeignKey("bom_version.version_id"), nullable=True)
    change_trigger = Column(String, nullable=True)

    bom_header = relationship("BOMHeader", back_populates="versions")
    source_version = relationship("BOMVersion", remote_side=[version_id])
    lines = relationship("BOMLine", back_populates="version")


class BOMLine(Base):
    __tablename__ = "bom_line"

    bom_line_id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("bom_version.version_id"), nullable=False, index=True)
    sequence = Column(Integer, nullable=False)
    component_system_item_code = Column(String, nullable=False, index=True)
    qty_per = Column(Float, nullable=False)
    uom = Column(String, nullable=False)
    scrap_rate = Column(Float, nullable=False, default=0)
    phantom_flag = Column(Boolean, nullable=False, default=False)
    alt_group = Column(Integer, nullable=True)
    alt_priority = Column(Integer, nullable=True)
    operation_id = Column(String, nullable=True)
    notes = Column(String, nullable=True)

    version = relationship("BOMVersion", back_populates="lines")


class WorkOrderBOMSnapshot(Base):
    __tablename__ = "work_order_bom_snapshot"

    id = Column(Integer, primary_key=True, index=True)
    work_order_no = Column(String, nullable=False, unique=True, index=True)
    parent_system_item_code = Column(String, nullable=False)
    work_order_qty = Column(Float, nullable=False)
    bom_version_id = Column(Integer, ForeignKey("bom_version.version_id"), nullable=False)
    status = Column(String, nullable=False, default="DRAFT")
    issue_status = Column(String, nullable=False, default="PENDING")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(String, nullable=True)
    released_by = Column(String, nullable=True)
    released_at = Column(DateTime, nullable=True)
    issued_by = Column(String, nullable=True)
    issued_at = Column(DateTime, nullable=True)

    bom_version = relationship("BOMVersion")


class WorkOrderBOMSnapshotLine(Base):
    __tablename__ = "work_order_bom_snapshot_line"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("work_order_bom_snapshot.id"), nullable=False, index=True)
    seq_no = Column(Integer, nullable=False)
    item_code = Column(String, nullable=False, index=True)
    item_name = Column(String, nullable=True)
    required_qty = Column(Float, nullable=False)
    uom = Column(String, nullable=False)


class MaterialIssueEvent(Base):
    __tablename__ = "material_issue_event"

    issue_event_id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("work_order_bom_snapshot.id"), nullable=False, index=True)
    work_order_no = Column(String, nullable=False, index=True)
    bom_version_id = Column(Integer, ForeignKey("bom_version.version_id"), nullable=False, index=True)
    org_id = Column(String, nullable=False, index=True)
    location_id = Column(String, nullable=False, index=True)
    issued_by = Column(String, nullable=False)
    issued_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MaterialIssueCorrectionEvent(Base):
    __tablename__ = "material_issue_correction_event"

    correction_event_id = Column(Integer, primary_key=True, index=True)
    original_issue_event_id = Column(Integer, ForeignKey("material_issue_event.issue_event_id"), nullable=False, index=True)
    snapshot_id = Column(Integer, ForeignKey("work_order_bom_snapshot.id"), nullable=False, index=True)
    work_order_no = Column(String, nullable=False, index=True)
    org_id = Column(String, nullable=False, index=True)
    location_id = Column(String, nullable=False, index=True)
    reason_code = Column(String, nullable=False, index=True)
    reason_note = Column(String, nullable=True)
    corrected_by = Column(String, nullable=False)
    corrected_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class RoutingHeader(Base):
    __tablename__ = "routing_header"

    id = Column(Integer, primary_key=True, index=True)
    item_code = Column(String, nullable=False, index=True)
    routing_code = Column(String, nullable=False, index=True)
    routing_name = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    steps = relationship(
        "RoutingStep",
        back_populates="routing",
        cascade="all, delete-orphan",
        order_by="RoutingStep.seq_no",
    )


class RoutingStep(Base):
    __tablename__ = "routing_step"
    __table_args__ = (
        UniqueConstraint("routing_id", "seq_no", name="uq_routing_step_routing_id_seq_no"),
    )

    id = Column(Integer, primary_key=True, index=True)
    routing_id = Column(Integer, ForeignKey("routing_header.id"), nullable=False, index=True)
    seq_no = Column(Integer, nullable=False)
    step_code = Column(String, nullable=False)
    step_name = Column(String, nullable=False)
    department = Column(String, nullable=True)
    is_required = Column(Boolean, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    routing = relationship("RoutingHeader", back_populates="steps")


class WorkOrderRoutingSnapshot(Base):
    __tablename__ = "work_order_routing_snapshot"

    id = Column(Integer, primary_key=True, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id"), nullable=False, unique=True, index=True)
    source_routing_id = Column(Integer, ForeignKey("routing_header.id"), nullable=False, index=True)
    routing_code = Column(String, nullable=False)
    routing_name = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    work_order = relationship("WorkOrder", back_populates="routing_snapshot")
    steps = relationship(
        "WorkOrderRoutingSnapshotStep",
        back_populates="snapshot",
        cascade="all, delete-orphan",
        order_by="WorkOrderRoutingSnapshotStep.seq_no",
    )


class WorkOrderRoutingSnapshotStep(Base):
    __tablename__ = "work_order_routing_snapshot_step"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(Integer, ForeignKey("work_order_routing_snapshot.id"), nullable=False, index=True)
    seq_no = Column(Integer, nullable=False)
    step_code = Column(String, nullable=False)
    step_name = Column(String, nullable=False)
    department = Column(String, nullable=True)
    is_required = Column(Boolean, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    snapshot = relationship("WorkOrderRoutingSnapshot", back_populates="steps")



