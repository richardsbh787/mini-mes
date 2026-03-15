from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from app.schemas.work_order_routing_execution_read import WorkOrderRoutingExecutionReadResponse
from app.services.work_order_routing_execution_read import build_work_order_routing_execution_read


router = APIRouter(prefix="/v2/work-order", tags=["v2-work-order-routing-execution-read"])


@router.get("/{work_order_id}/routing-execution", response_model=WorkOrderRoutingExecutionReadResponse)
def work_order_routing_execution_read(work_order_id: int, db: Session = Depends(get_db)):
    return build_work_order_routing_execution_read(db=db, work_order_id=work_order_id)
