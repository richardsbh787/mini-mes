
# main.py
from __future__ import annotations

from app.services.consume_service import commit_consume
from app.infra.load_env import load_env_if_needed
load_env_if_needed()
from datetime import datetime
from decimal import Decimal
from typing import List
from app.services.consume_service import preview_consume
from app.repositories.stock_ledger_repo import get_onhand
from app.services.inventory_adjustment_service import commit_adjustment



from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session

from database import engine, get_db

# ✅ Consumption Engine (v2)
from consumption_engine import ConsumptionRequest, build_ledger_entry

# ✅ Models (只 import 一次，不要重复)
from models import (
    Base,
    # Masters
    Product,
    SalesOrder,
    ProductionLine,
    WorkOrder,
    ProductionEvent,
    Inventory,
    RawMaterial,
    RawMaterialInventory,
    BOM,
    # Logs / Transactions
    ProductionLog,
    MaterialTransaction,
    InventoryTransaction,
    StockLedger,
)

# ✅ Schemas (只 import 一次，不要重复)
from schemas import (
    # Product
    ProductCreate,
    ProductResponse,
    # Sales Order
    SalesOrderCreate,
    SalesOrderResponse,
    # Line
    ProductionLineCreate,
    ProductionLineResponse,
    # Work Order
    WorkOrderCreate,
    WorkOrderResponse,
    # Event
    ProductionEventCreate,
    ProductionEventResponse,
    # Inventory
    InventoryCreate,
    InventoryResponse,
    # Raw Material
    RawMaterialCreate,
    RawMaterialResponse,
    # BOM
    BOMCreate,
    BOMResponse,
    # Production Log
    ProductionLogCreate,
)

# ✅ Capacity Engine
from capacity_engine import simulate_line_orders, calculate_line_capacity

print(">>> USING THIS MAIN FILE <<<")

# ==========================
# App Init
# ==========================
app = FastAPI()

# ✅ 关键：确保所有 models 都被 import 后，再 create_all
Base.metadata.create_all(bind=engine)

# ==========================
# Root
# ==========================
@app.get("/")
def root():
    return {"message": "Mini-MES Running (Event Enabled)"}


# ==========================================================
# V2: Consume (Preview / Commit) + Stock Ledger Query
# ==========================================================
@app.post("/v2/consume/preview")
def consume_preview(
    org_uuid: str,
    item_id: str,
    qty: Decimal,
):
    payload = {
        "org_id": org_uuid,
        "item_id": item_id,
        "qty": float(qty),
        "uom": "ea",
    }
    return preview_consume(payload)


@app.post("/v2/consume/commit")
def consume_commit(
    org_uuid: str,
    item_id: str,
    qty: Decimal,
):
    payload = {
        "org_id": org_uuid,
        "item_id": item_id,
        "qty": float(qty),
        "uom": "ea",
    }
    return commit_consume(payload)

from app.repositories.stock_ledger_repo import list_ledger

@app.get("/v2/stock-ledger")
def get_stock_ledger(org_uuid: str, limit: int = 20):
    return list_ledger(org_id=org_uuid, limit=limit)

@app.get("/v2/stock/onhand")
def stock_onhand(org_uuid: str, item_id: str):
    return {"org_id": org_uuid, "item_id": item_id, "onhand_qty": get_onhand(org_uuid, item_id)}

@app.post("/v2/inventory-adjustment/commit")
def inventory_adjustment_commit(org_uuid: str, item_id: str, qty: Decimal):
    payload = {
        "org_id": org_uuid,
        "adj_type": "701",
        "reason": "manual",
        "lines": [
            {"item_id": item_id, "qty": float(qty), "uom": "ea", "note": "test adjustment"}
        ],
    }
    return commit_adjustment(payload)


# ==========================
# Product API
# ==========================
@app.post("/products", response_model=ProductResponse)
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    db_product = Product(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


@app.get("/products", response_model=List[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    return db.query(Product).all()


# ==========================
# Sales Order API
# ==========================
@app.post("/sales-orders", response_model=SalesOrderResponse)
def create_sales_order(order: SalesOrderCreate, db: Session = Depends(get_db)):
    db_order = SalesOrder(
        order_no=order.order_no,
        customer_name=order.customer_name,
        order_date=order.order_date,
        shipment_date=order.shipment_date,
        status="OPEN",
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order


@app.get("/sales-orders", response_model=List[SalesOrderResponse])
def get_sales_orders(db: Session = Depends(get_db)):
    return db.query(SalesOrder).all()


# ==========================
# Production Line API
# ==========================
@app.post("/production-lines", response_model=ProductionLineResponse)
def create_production_line(line: ProductionLineCreate, db: Session = Depends(get_db)):
    existing = db.query(ProductionLine).filter(ProductionLine.line_name == line.line_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Production line name already exists")

    db_line = ProductionLine(**line.model_dump())
    db.add(db_line)
    db.commit()
    db.refresh(db_line)
    return db_line


@app.get("/production-lines", response_model=List[ProductionLineResponse])
def get_production_lines(db: Session = Depends(get_db)):
    return db.query(ProductionLine).all()


# ==========================
# Work Order API
# ==========================
@app.post("/work-orders", response_model=WorkOrderResponse)
def create_work_order(work_order: WorkOrderCreate, db: Session = Depends(get_db)):
    line = db.query(ProductionLine).filter(ProductionLine.id == work_order.production_line_id).first()
    if not line:
        raise HTTPException(status_code=404, detail="Production line not found")

    status = "OPEN" if work_order.is_material_ready else "BLOCKED_MATERIAL"

    db_work_order = WorkOrder(
        work_order_no=work_order.work_order_no,
        sales_order_id=work_order.sales_order_id,
        product_id=work_order.product_id,
        production_line_id=work_order.production_line_id,
        planned_hours=work_order.planned_hours,
        remaining_hours=work_order.planned_hours,
        priority=work_order.priority,
        promise_date=work_order.promise_date,
        is_material_ready=work_order.is_material_ready,
        material_ready_date=work_order.material_ready_date,
        status=status,
    )
    db.add(db_work_order)
    db.commit()
    db.refresh(db_work_order)
    return db_work_order


@app.get("/work-orders", response_model=List[WorkOrderResponse])
def get_work_orders(db: Session = Depends(get_db)):
    return db.query(WorkOrder).all()


# ================================
# Capacity API
# ================================
@app.get("/production-lines/{line_id}/capacity")
def get_line_capacity(line_id: int, forecast_days: int = 5, db: Session = Depends(get_db)):
    line = db.query(ProductionLine).filter(ProductionLine.id == line_id).first()
    if not line:
        raise HTTPException(status_code=404, detail="Production Line not found")

    work_orders = db.query(WorkOrder).filter(WorkOrder.production_line_id == line_id).all()
    events = db.query(ProductionEvent).filter(
        ProductionEvent.production_line_id == line_id,
        ProductionEvent.is_resolved == False,
    ).all()

    return calculate_line_capacity(line, work_orders, events, forecast_days)


@app.get("/production-lines/{line_id}/simulation")
def simulate_orders(line_id: int, db: Session = Depends(get_db)):
    line = db.query(ProductionLine).filter(ProductionLine.id == line_id).first()
    if not line:
        raise HTTPException(status_code=404, detail="Production Line not found")

    work_orders = db.query(WorkOrder).filter(WorkOrder.production_line_id == line_id).all()
    events = db.query(ProductionEvent).filter(
        ProductionEvent.production_line_id == line_id,
        ProductionEvent.is_resolved == False,
    ).all()

    return simulate_line_orders(line, work_orders, events)


# ==========================
# Production Log API (含：SAP261 扣料 + StockLedger)
# ==========================
@app.post("/production-log", response_model=WorkOrderResponse)
def log_production(log: ProductionLogCreate, db: Session = Depends(get_db)):
    if log.produced_hours <= 0:
        raise HTTPException(status_code=400, detail="Produced hours must be positive")
    if log.log_date > datetime.utcnow().date():
        raise HTTPException(status_code=400, detail="Log date cannot be in the future")

    work_order = db.query(WorkOrder).filter(WorkOrder.id == log.work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail="Work order not found")

    if work_order.status in ["DONE", "BLOCKED", "BLOCKED_MATERIAL"]:
        raise HTTPException(status_code=400, detail="Work order not executable")

    if work_order.production_line_id != log.production_line_id:
        raise HTTPException(status_code=400, detail="Production line mismatch")

    produced_hours = log.produced_hours
    if produced_hours > work_order.remaining_hours:
        produced_hours = work_order.remaining_hours

    # ==========================================================
    # 1️⃣ 扣原料 (SAP 261) + 写 StockLedger
    # ==========================================================
    bom_items = db.query(BOM).filter(BOM.product_id == work_order.product_id).all()
    if not bom_items:
        raise HTTPException(status_code=400, detail="No BOM defined")

    for item in bom_items:
        consumption_hours = produced_hours + log.scrap_hours
        if log.rework_consumes_material:
            consumption_hours += log.rework_hours

        required_qty = float(consumption_hours) * float(item.quantity_required)

        material_inventory = db.query(RawMaterialInventory).filter(
            RawMaterialInventory.raw_material_id == item.raw_material_id
        ).first()
        if not material_inventory:
            raise HTTPException(status_code=400, detail="Raw material inventory missing")

        if material_inventory.quantity_on_hand < required_qty:
            raise HTTPException(status_code=400, detail=f"Insufficient raw material ID {item.raw_material_id}")

        material_inventory.quantity_on_hand -= required_qty

        db.add(MaterialTransaction(
            raw_material_id=item.raw_material_id,
            work_order_id=work_order.id,
            quantity=required_qty,
            transaction_type="CONSUME",
        ))

        db.add(InventoryTransaction(
            item_type="RAW",
            item_id=item.raw_material_id,
            transaction_type="CONSUME",
            quantity=required_qty,
            reference_id=work_order.id,
        ))

        # ✅ 用原料主数据的 material_code + unit
        rm = db.query(RawMaterial).filter(RawMaterial.id == item.raw_material_id).first()
        if not rm:
            raise HTTPException(status_code=400, detail=f"Raw material master not found: {item.raw_material_id}")

        db.add(StockLedger(
            org_id="demo-org",                  # 先写死，后续做 multi-tenant 再换
            item_id=rm.material_code,           # ✅ RM-DEMO-001
            location_id=None,
            txn_type="ISSUE",
            qty=float(required_qty),
            uom=rm.unit or "PCS",
            ref_type="work_order",
            ref_id=str(work_order.id),
            note="auto consume from production-log",
            occurred_at=datetime.utcnow(),
        ))

    # ==========================================================
    # 2️⃣ 更新工单工时
    # ==========================================================
    work_order.remaining_hours -= produced_hours
    work_order.actual_hours += produced_hours

    if work_order.status == "OPEN":
        work_order.status = "RUNNING"
        work_order.started_at = datetime.utcnow()

    # ==========================================================
    # 3️⃣ 完工 → 成品入库 (SAP 101)
    # ==========================================================
    if work_order.remaining_hours <= 0:
        work_order.remaining_hours = 0
        work_order.status = "DONE"
        work_order.completed_at = datetime.utcnow()

        inv = db.query(Inventory).filter(Inventory.product_id == work_order.product_id).first()
        if not inv:
            inv = Inventory(product_id=work_order.product_id, quantity_on_hand=0)
            db.add(inv)
            db.flush()

        receive_qty = 1
        inv.quantity_on_hand += receive_qty

        db.add(InventoryTransaction(
            item_type="FINISHED",
            item_id=work_order.product_id,
            transaction_type="RECEIVE",
            quantity=receive_qty,
            reference_id=work_order.id,
        ))

    # ==========================================================
    # 4️⃣ 写生产日志
    # ==========================================================
    db.add(ProductionLog(
        production_line_id=log.production_line_id,
        work_order_id=log.work_order_id,
        produced_hours=produced_hours,
        scrap_hours=log.scrap_hours,
        rework_hours=log.rework_hours,
        rework_consumes_material=log.rework_consumes_material,
        log_date=log.log_date,
    ))

    # ==========================================================
    # 5️⃣ Commit
    # ==========================================================
    try:
        db.commit()
        db.refresh(work_order)
    except:
        db.rollback()
        raise HTTPException(status_code=500, detail="Production log failed")

    return work_order


# ==========================
# Production Event API
# ==========================
@app.post("/production-events", response_model=ProductionEventResponse)
def create_production_event(event: ProductionEventCreate, db: Session = Depends(get_db)):
    if event.impact_hours <= 0:
        raise HTTPException(status_code=400, detail="Impact hours must be positive")
    if event.event_date > datetime.utcnow().date():
        raise HTTPException(status_code=400, detail="Event date cannot be in the future")

    line = db.query(ProductionLine).filter(ProductionLine.id == event.production_line_id).first()
    if not line:
        raise HTTPException(status_code=404, detail="Production line not found")

    db_event = ProductionEvent(
        production_line_id=event.production_line_id,
        event_type=event.event_type,
        impact_hours=event.impact_hours,
        description=event.description,
        event_date=event.event_date,
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


@app.post("/production-events/{event_id}/resolve")
def resolve_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(ProductionEvent).filter(ProductionEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.is_resolved:
        raise HTTPException(status_code=400, detail="Event already resolved")

    event.is_resolved = True
    event.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(event)
    return {"message": "Event resolved", "event_id": event.id}


# ==========================
# Inventory API
# ==========================
@app.post("/inventory", response_model=InventoryResponse)
def create_inventory(record: InventoryCreate, db: Session = Depends(get_db)):
    existing = db.query(Inventory).filter(Inventory.product_id == record.product_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Inventory already exists for this product")

    inv = Inventory(product_id=record.product_id, quantity_on_hand=record.quantity_on_hand)
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


@app.get("/inventory", response_model=List[InventoryResponse])
def get_inventory(db: Session = Depends(get_db)):
    return db.query(Inventory).all()


# ==========================
# Shipment API
# ==========================
@app.post("/ship/{sales_order_id}")
def ship_order(sales_order_id: int, db: Session = Depends(get_db)):
    so = db.query(SalesOrder).filter(SalesOrder.id == sales_order_id).first()
    if not so:
        raise HTTPException(status_code=404, detail="Sales order not found")
    if so.status == "SHIPPED":
        raise HTTPException(status_code=400, detail="Already shipped")

    work_orders = db.query(WorkOrder).filter(WorkOrder.sales_order_id == sales_order_id).all()
    if not work_orders:
        raise HTTPException(status_code=400, detail="No work orders found")

    for wo in work_orders:
        if wo.status != "DONE":
            raise HTTPException(status_code=400, detail=f"Work order {wo.work_order_no} not completed")

    for wo in work_orders:
        inv = db.query(Inventory).filter(Inventory.product_id == wo.product_id).first()
        if not inv:
            raise HTTPException(status_code=400, detail="Inventory not found")
        if inv.quantity_on_hand < 1:
            raise HTTPException(status_code=400, detail="Insufficient inventory")
        inv.quantity_on_hand -= 1

    so.status = "SHIPPED"
    so.shipment_date = datetime.utcnow().date()
    db.commit()

    return {"message": "Order shipped successfully", "sales_order_id": so.id}


# ==========================
# Raw Material API
# ==========================
@app.post("/raw-materials", response_model=RawMaterialResponse)
def create_raw_material(material: RawMaterialCreate, db: Session = Depends(get_db)):
    existing = db.query(RawMaterial).filter(RawMaterial.material_code == material.material_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Material code already exists")

    rm = RawMaterial(
        material_code=material.material_code,
        material_name=material.material_name,
        unit=material.unit,
    )
    db.add(rm)
    db.commit()
    db.refresh(rm)

    inv = RawMaterialInventory(raw_material_id=rm.id, quantity_on_hand=0)
    db.add(inv)
    db.commit()

    return rm


@app.get("/raw-materials", response_model=List[RawMaterialResponse])
def get_raw_materials(db: Session = Depends(get_db)):
    return db.query(RawMaterial).all()


# ==========================
# BOM API
# ==========================
@app.post("/boms", response_model=BOMResponse)
def create_bom(bom: BOMCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == bom.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    material = db.query(RawMaterial).filter(RawMaterial.id == bom.raw_material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="Raw material not found")

    db_bom = BOM(
        product_id=bom.product_id,
        raw_material_id=bom.raw_material_id,
        quantity_required=bom.quantity_required,
    )
    db.add(db_bom)
    db.commit()
    db.refresh(db_bom)
    return db_bom


@app.get("/boms", response_model=List[BOMResponse])
def get_boms(db: Session = Depends(get_db)):
    return db.query(BOM).all()


# ==========================
# Inventory Transaction API
# ==========================
@app.get("/inventory-transactions")
def get_inventory_transactions(db: Session = Depends(get_db)):
    return db.query(InventoryTransaction).order_by(InventoryTransaction.created_at.desc()).all()


from app.api.v2.model_routing import router as model_routing_router
app.include_router(model_routing_router)




