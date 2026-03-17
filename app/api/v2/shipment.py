from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.work_order_shipment import WorkOrderShipmentCreateRequest, WorkOrderShipmentResponse
from app.services.work_order_shipment import create_work_order_shipment, get_work_order_shipment, list_work_order_shipments
from database import get_db


router = APIRouter(tags=["v2-work-order-shipment"])


@router.post("/work-orders/{work_order_id}/shipments", response_model=WorkOrderShipmentResponse)
def work_order_shipment_create(
    work_order_id: int,
    payload: WorkOrderShipmentCreateRequest,
    db: Session = Depends(get_db),
):
    return create_work_order_shipment(db=db, work_order_id=work_order_id, payload=payload)


@router.get("/work-orders/{work_order_id}/shipments", response_model=list[WorkOrderShipmentResponse])
def work_order_shipment_list(
    work_order_id: int,
    db: Session = Depends(get_db),
):
    return list_work_order_shipments(db=db, work_order_id=work_order_id)


@router.get("/shipments/{shipment_id}", response_model=WorkOrderShipmentResponse)
def work_order_shipment_detail(
    shipment_id: int,
    db: Session = Depends(get_db),
):
    return get_work_order_shipment(db=db, shipment_id=shipment_id)
