from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import WorkOrder
from schemas import WorkOrderResponse
from app.schemas.work_order_routing_bind import WorkOrderRoutingBindRequest
from app.services.work_order_routing_binding import bind_work_order_to_routing


router = APIRouter(prefix="/v2/work-order", tags=["v2-work-order-routing-bind"])


@router.post("/routing-bind", response_model=WorkOrderResponse)
def work_order_routing_bind(payload: WorkOrderRoutingBindRequest, db: Session = Depends(get_db)):
    work_order = db.query(WorkOrder).filter(WorkOrder.id == payload.work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail=f"WorkOrder not found: id={payload.work_order_id}")

    return bind_work_order_to_routing(db=db, work_order=work_order, routing_id=payload.routing_id)
