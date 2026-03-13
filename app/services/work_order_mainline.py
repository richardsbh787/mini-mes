from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session, selectinload

from models import ProductionLine, RoutingHeader, WorkOrder, WorkOrderRoutingSnapshot
from schemas import WorkOrderCreate, WorkOrderResponse
from app.services.work_order_read_surface import build_work_order_response
from app.services.work_order_routing_snapshot import create_work_order_routing_snapshot
from app.services.work_order_routing_binding import validate_routing_binding


def create_work_order_record(db: Session, work_order: WorkOrderCreate) -> WorkOrderResponse:
    line = db.query(ProductionLine).filter(ProductionLine.id == work_order.production_line_id).first()
    if not line:
        raise HTTPException(status_code=404, detail="Production line not found")

    bound_routing = None
    if work_order.routing_id is not None:
        bound_routing = validate_routing_binding(
            db=db,
            product_id=work_order.product_id,
            routing_id=work_order.routing_id,
        )

    status = "OPEN" if work_order.is_material_ready else "BLOCKED_MATERIAL"

    db_work_order = WorkOrder(
        work_order_no=work_order.work_order_no,
        sales_order_id=work_order.sales_order_id,
        product_id=work_order.product_id,
        production_line_id=work_order.production_line_id,
        routing_id=work_order.routing_id,
        planned_hours=work_order.planned_hours,
        remaining_hours=work_order.planned_hours,
        priority=work_order.priority,
        promise_date=work_order.promise_date,
        is_material_ready=work_order.is_material_ready,
        material_ready_date=work_order.material_ready_date,
        status=status,
    )
    db.add(db_work_order)
    db.flush()

    if bound_routing is not None:
        create_work_order_routing_snapshot(db=db, work_order=db_work_order, routing=bound_routing)

    db.commit()
    db.refresh(db_work_order)
    return build_work_order_response(db_work_order)


def list_work_order_reads(db: Session) -> list[WorkOrderResponse]:
    rows = (
        db.query(WorkOrder)
        .options(selectinload(WorkOrder.routing).selectinload(RoutingHeader.steps))
        .options(selectinload(WorkOrder.routing_snapshot).selectinload(WorkOrderRoutingSnapshot.steps))
        .all()
    )
    return [build_work_order_response(row) for row in rows]
