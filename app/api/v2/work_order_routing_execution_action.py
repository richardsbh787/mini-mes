from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from app.schemas.work_order_routing_execution_action import (
    WorkOrderRoutingExecutionActionResponse,
    WorkOrderRoutingExecutionReleaseActionRequest,
    WorkOrderRoutingExecutionStartActionRequest,
)
from app.services.work_order_routing_execution_action import (
    release_work_order_routing_execution_action,
    start_work_order_routing_execution_action,
)


router = APIRouter(prefix="/v2/work-order/routing-execution", tags=["v2-work-order-routing-execution-action"])


@router.post("/start", response_model=WorkOrderRoutingExecutionActionResponse)
def work_order_routing_execution_start(
    payload: WorkOrderRoutingExecutionStartActionRequest,
    db: Session = Depends(get_db),
):
    return start_work_order_routing_execution_action(
        db=db,
        work_order_id=payload.work_order_id,
        step_code=payload.step_code,
        seq_no=payload.seq_no,
        started_by=payload.started_by,
    )


@router.post("/release", response_model=WorkOrderRoutingExecutionActionResponse)
def work_order_routing_execution_release(
    payload: WorkOrderRoutingExecutionReleaseActionRequest,
    db: Session = Depends(get_db),
):
    return release_work_order_routing_execution_action(
        db=db,
        work_order_id=payload.work_order_id,
        step_code=payload.step_code,
        seq_no=payload.seq_no,
        completed_by=payload.completed_by,
    )
