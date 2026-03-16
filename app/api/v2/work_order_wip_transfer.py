from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.work_order_wip_transfer import (
    WorkOrderWipTransferCreateRequest,
    WorkOrderWipTransferResponse,
)
from app.services.work_order_wip_transfer import (
    create_work_order_wip_transfer,
    get_work_order_wip_transfer,
    list_work_order_wip_transfers,
)
from database import get_db


router = APIRouter(tags=["v2-work-order-wip-transfer"])


@router.post("/work-orders/{work_order_id}/wip-transfers", response_model=WorkOrderWipTransferResponse)
def work_order_wip_transfer_create(
    work_order_id: int,
    payload: WorkOrderWipTransferCreateRequest,
    db: Session = Depends(get_db),
):
    return create_work_order_wip_transfer(db=db, work_order_id=work_order_id, payload=payload)


@router.get("/work-orders/{work_order_id}/wip-transfers", response_model=list[WorkOrderWipTransferResponse])
def work_order_wip_transfer_list(
    work_order_id: int,
    db: Session = Depends(get_db),
):
    return list_work_order_wip_transfers(db=db, work_order_id=work_order_id)


@router.get("/wip-transfers/{transfer_id}", response_model=WorkOrderWipTransferResponse)
def work_order_wip_transfer_detail(
    transfer_id: int,
    db: Session = Depends(get_db),
):
    return get_work_order_wip_transfer(db=db, transfer_id=transfer_id)
