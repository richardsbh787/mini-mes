from models import InventoryTransaction
from models import MaterialTransaction, RawMaterialInventory
from models import BOM
from schemas import BOMCreate, BOMResponse
print(">>> USING THIS MAIN FILE <<<")
from models import Inventory
from schemas import InventoryCreate, InventoryResponse
from datetime import datetime
from models import ProductionLog
from schemas import ProductionLogCreate
from capacity_engine import simulate_line_orders, calculate_line_capacity
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import engine, get_db
from models import (
    Base,
    Product,
    SalesOrder,
    ProductionLine,
    WorkOrder,
    ProductionEvent,   # ✅ 必须加
)

from schemas import (
    ProductCreate,
    ProductResponse,
    SalesOrderCreate,
    SalesOrderResponse,
    ProductionLineCreate,
    ProductionLineResponse,
    WorkOrderCreate,
    WorkOrderResponse,
    ProductionEventCreate,
    ProductionEventResponse,
    RawMaterialCreate,
    RawMaterialResponse,
)

# ==========================
# App Init
# ==========================

app = FastAPI()
Base.metadata.create_all(bind=engine)


# ==========================
# Root
# ==========================

@app.get("/")
def root():
    return {"message": "Mini-MES Running (Event Enabled)"}


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


@app.get("/products", response_model=list[ProductResponse])
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
        status="OPEN"   # ✅ 强制写入
    )

    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    return db_order


@app.get("/sales-orders", response_model=list[SalesOrderResponse])
def get_sales_orders(db: Session = Depends(get_db)):
    return db.query(SalesOrder).all()


# ==========================
# Production Line API
# ==========================

@app.post("/production-lines", response_model=ProductionLineResponse)
def create_production_line(line: ProductionLineCreate, db: Session = Depends(get_db)):

    # ==========================
    # Duplicate Name Protection
    # ==========================
    existing_line = db.query(ProductionLine).filter(
        ProductionLine.line_name == line.line_name
    ).first()

    if existing_line:
        raise HTTPException(
            status_code=400,
            detail="Production line name already exists"
        )

    db_line = ProductionLine(**line.model_dump())

    try:
        db.add(db_line)
        db.commit()
        db.refresh(db_line)
    except:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create production line")

    return db_line


@app.get("/production-lines", response_model=list[ProductionLineResponse])
def get_production_lines(db: Session = Depends(get_db)):
    return db.query(ProductionLine).all()


# ==========================
# Work Order API (Material Gate Enabled)
# ==========================

@app.post("/work-orders", response_model=WorkOrderResponse)
def create_work_order(work_order: WorkOrderCreate, db: Session = Depends(get_db)):

    production_line = db.query(ProductionLine).filter(
        ProductionLine.id == work_order.production_line_id
    ).first()

    if not production_line:
        raise HTTPException(status_code=404, detail="Production line not found")

    status = "OPEN"
    if not work_order.is_material_ready:
        status = "BLOCKED_MATERIAL"

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
        status=status
    )

    db.add(db_work_order)
    db.commit()
    db.refresh(db_work_order)

    return db_work_order


@app.get("/work-orders", response_model=list[WorkOrderResponse])
def get_work_orders(db: Session = Depends(get_db)):
    return db.query(WorkOrder).all()


# ================================
# Capacity API (Auto Reallocation Enabled)
# ================================

@app.get("/production-lines/{line_id}/capacity")
def get_line_capacity(
    line_id: int,
    forecast_days: int = 5,
    db: Session = Depends(get_db),
):

    production_line = db.query(ProductionLine).filter(
        ProductionLine.id == line_id
    ).first()

    if not production_line:
        raise HTTPException(status_code=404, detail="Production Line not found")

    work_orders = db.query(WorkOrder).filter(
        WorkOrder.production_line_id == line_id
    ).all()

    production_events = db.query(ProductionEvent).filter(
        ProductionEvent.production_line_id == line_id,
        ProductionEvent.is_resolved == False
    ).all()


    result = calculate_line_capacity(
       production_line,
       work_orders,
       production_events,
       forecast_days
)

    return result


# ==========================
# Simulation API
# ==========================

@app.get("/production-lines/{line_id}/simulation")
def simulate_orders(line_id: int, db: Session = Depends(get_db)):

    production_line = db.query(ProductionLine).filter(
        ProductionLine.id == line_id
    ).first()

    if not production_line:
        raise HTTPException(
            status_code=404,
            detail="Production Line not found"
        )

    work_orders = db.query(WorkOrder).filter(
        WorkOrder.production_line_id == line_id
    ).all()

    production_events = db.query(ProductionEvent).filter(
        ProductionEvent.production_line_id == line_id,
        ProductionEvent.is_resolved == False
    ).all()

    result = simulate_line_orders(
        production_line,
        work_orders,
        production_events
    )

    return result



@app.post("/production-log", response_model=WorkOrderResponse)
def log_production(log: ProductionLogCreate, db: Session = Depends(get_db)):

    # ==========================
    # 基础检查
    # ==========================
    if log.produced_hours <= 0:
        raise HTTPException(status_code=400, detail="Produced hours must be positive")

    if log.log_date > datetime.utcnow().date():
        raise HTTPException(status_code=400, detail="Log date cannot be in the future")

    work_order = db.query(WorkOrder).filter(
        WorkOrder.id == log.work_order_id
    ).first()

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
    # 1️⃣ 扣原料 (SAP 261)
    # ==========================================================

    bom_items = db.query(BOM).filter(
        BOM.product_id == work_order.product_id
    ).all()

    if not bom_items:
        raise HTTPException(status_code=400, detail="No BOM defined")

    for item in bom_items:

        consumption_hours = produced_hours + log.scrap_hours

        if log.rework_consumes_material:
            consumption_hours += log.rework_hours

        required_qty = consumption_hours * item.quantity_required

        material_inventory = db.query(RawMaterialInventory).filter(
            RawMaterialInventory.raw_material_id == item.raw_material_id
        ).first()

        if not material_inventory:
            raise HTTPException(status_code=400, detail="Raw material inventory missing")

        if material_inventory.quantity_on_hand < required_qty:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient raw material ID {item.raw_material_id}"
            )

        material_inventory.quantity_on_hand -= required_qty

        db.add(MaterialTransaction(
            raw_material_id=item.raw_material_id,
            work_order_id=work_order.id,
            quantity=required_qty,
            transaction_type="CONSUME"
        ))

        db.add(InventoryTransaction(
            item_type="RAW",
            item_id=item.raw_material_id,
            transaction_type="CONSUME",
            quantity=required_qty,
            reference_id=work_order.id
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
    # 3️⃣ 如果完工 → 成品入库 (SAP 101)
    # ==========================================================

    if work_order.remaining_hours <= 0:

        work_order.remaining_hours = 0
        work_order.status = "DONE"
        work_order.completed_at = datetime.utcnow()

        inventory = db.query(Inventory).filter(
            Inventory.product_id == work_order.product_id
        ).first()

        if not inventory:

            inventory = Inventory(
                product_id=work_order.product_id,
                quantity_on_hand=0
            )

            db.add(inventory)
            db.flush()

        receive_qty = 1

        inventory.quantity_on_hand += receive_qty

        db.add(InventoryTransaction(
            item_type="FINISHED",
            item_id=work_order.product_id,
            transaction_type="RECEIVE",
            quantity=receive_qty,
            reference_id=work_order.id
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
        log_date=log.log_date
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







@app.post("/production-events/{event_id}/resolve")
def resolve_event(event_id: int, db: Session = Depends(get_db)):

    event = db.query(ProductionEvent).filter(
        ProductionEvent.id == event_id
    ).first()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.is_resolved:
        raise HTTPException(status_code=400, detail="Event already resolved")

    event.is_resolved = True
    event.resolved_at = datetime.utcnow()

    db.commit()
    db.refresh(event)

    return {"message": "Event resolved", "event_id": event.id}



@app.post("/production-events", response_model=ProductionEventResponse)
def create_production_event(event: ProductionEventCreate, db: Session = Depends(get_db)):

    if event.impact_hours <= 0:
        raise HTTPException(status_code=400, detail="Impact hours must be positive")

    if event.event_date > datetime.utcnow().date():
        raise HTTPException(status_code=400, detail="Event date cannot be in the future")

    line = db.query(ProductionLine).filter(
        ProductionLine.id == event.production_line_id
    ).first()

    if not line:
        raise HTTPException(status_code=404, detail="Production line not found")

    db_event = ProductionEvent(
        production_line_id=event.production_line_id,
        event_type=event.event_type,
        impact_hours=event.impact_hours,
        description=event.description,
        event_date=event.event_date
    )

    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    return db_event


# ==========================================================
# Inventory API
# ==========================================================

@app.post("/inventory", response_model=InventoryResponse)
def create_inventory(record: InventoryCreate, db: Session = Depends(get_db)):

    existing = db.query(Inventory).filter(
        Inventory.product_id == record.product_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Inventory already exists for this product")

    inventory = Inventory(
        product_id=record.product_id,
        quantity_on_hand=record.quantity_on_hand
    )

    db.add(inventory)
    db.commit()
    db.refresh(inventory)

    return inventory


@app.get("/inventory", response_model=list[InventoryResponse])
def get_inventory(db: Session = Depends(get_db)):
    return db.query(Inventory).all()



# ==========================================================
# Shipment API
# ==========================================================

@app.post("/ship/{sales_order_id}")
def ship_order(sales_order_id: int, db: Session = Depends(get_db)):

    sales_order = db.query(SalesOrder).filter(
        SalesOrder.id == sales_order_id
    ).first()

    if not sales_order:
        raise HTTPException(status_code=404, detail="Sales order not found")

    if sales_order.status == "SHIPPED":
        raise HTTPException(status_code=400, detail="Already shipped")

    # 找该订单的工单
    work_orders = db.query(WorkOrder).filter(
        WorkOrder.sales_order_id == sales_order_id
    ).all()

    if not work_orders:
        raise HTTPException(status_code=400, detail="No work orders found")

    # 检查是否全部 DONE
    for wo in work_orders:
        if wo.status != "DONE":
            raise HTTPException(
                status_code=400,
                detail=f"Work order {wo.work_order_no} not completed"
            )

    # 扣库存
    for wo in work_orders:

        inventory = db.query(Inventory).filter(
            Inventory.product_id == wo.product_id
        ).first()

        if not inventory:
            raise HTTPException(
                status_code=400,
                detail="Inventory not found"
            )

        if inventory.quantity_on_hand < 1:
            raise HTTPException(
                status_code=400,
                detail="Insufficient inventory"
            )

        inventory.quantity_on_hand -= 1

    sales_order.status = "SHIPPED"
    sales_order.shipment_date = datetime.utcnow().date()

    db.commit()

    return {
        "message": "Order shipped successfully",
        "sales_order_id": sales_order.id
    }




# ==========================================================
# Raw Material API
# ==========================================================

from models import RawMaterial, RawMaterialInventory, BOM
from schemas import (
    RawMaterialCreate,
    RawMaterialResponse,
    BOMCreate,
    BOMResponse,
)


@app.post("/raw-materials", response_model=RawMaterialResponse)
def create_raw_material(material: RawMaterialCreate, db: Session = Depends(get_db)):

    # 防重复 material_code
    existing = db.query(RawMaterial).filter(
        RawMaterial.material_code == material.material_code
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Material code already exists")

    # 创建原料
    db_material = RawMaterial(
        material_code=material.material_code,
        material_name=material.material_name,
        unit=material.unit
    )

    db.add(db_material)
    db.commit()
    db.refresh(db_material)

    # 自动创建库存记录
    inventory = RawMaterialInventory(
        raw_material_id=db_material.id,
        quantity_on_hand=0
    )

    db.add(inventory)
    db.commit()

    return db_material


@app.get("/raw-materials", response_model=list[RawMaterialResponse])
def get_raw_materials(db: Session = Depends(get_db)):
    return db.query(RawMaterial).all()


# ==========================================================
# BOM API
# ==========================================================

@app.post("/boms", response_model=BOMResponse)
def create_bom(bom: BOMCreate, db: Session = Depends(get_db)):

    # 检查 product 是否存在
    product = db.query(Product).filter(
        Product.id == bom.product_id
    ).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # 检查 raw material 是否存在
    material = db.query(RawMaterial).filter(
        RawMaterial.id == bom.raw_material_id
    ).first()

    if not material:
        raise HTTPException(status_code=404, detail="Raw material not found")

    # 创建 BOM
    db_bom = BOM(
        product_id=bom.product_id,
        raw_material_id=bom.raw_material_id,
        quantity_required=bom.quantity_required
    )

    db.add(db_bom)
    db.commit()
    db.refresh(db_bom)

    return db_bom


@app.get("/boms", response_model=list[BOMResponse])
def get_boms(db: Session = Depends(get_db)):
    return db.query(BOM).all()


# ==========================================================
# Inventory Transaction API (SAP Movement History)
# ==========================================================

from models import InventoryTransaction


@app.get("/inventory-transactions")
def get_inventory_transactions(db: Session = Depends(get_db)):

    return db.query(InventoryTransaction).order_by(
        InventoryTransaction.created_at.desc()
    ).all()




