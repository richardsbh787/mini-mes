from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models import RoutingHeader, RoutingStep
from app.schemas.routing_maintenance import (
    RoutingHeaderCreate,
    RoutingHeaderDetail,
    RoutingHeaderOut,
    RoutingStepCreate,
    RoutingStepOut,
)


router = APIRouter(prefix="/v2/routing-maintenance", tags=["v2-routing-maintenance"])
ROUTING_ALLOWED_STATUS = {"ACTIVE", "INACTIVE"}


def _normalize_required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    return normalized


@router.post("/headers", response_model=RoutingHeaderOut)
def create_routing_header(payload: RoutingHeaderCreate, db: Session = Depends(get_db)):
    item_code = _normalize_required_text(payload.item_code, "item_code")
    routing_code = _normalize_required_text(payload.routing_code, "routing_code")
    routing_name = _normalize_required_text(payload.routing_name, "routing_name")

    header_status = payload.status.strip().upper()
    if header_status not in ROUTING_ALLOWED_STATUS:
        raise HTTPException(status_code=400, detail="RoutingHeader.status must be ACTIVE or INACTIVE")

    row = RoutingHeader(
        item_code=item_code,
        routing_code=routing_code,
        routing_name=routing_name,
        status=header_status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.post("/headers/{routing_id}/steps", response_model=RoutingStepOut)
def create_routing_step(routing_id: int, payload: RoutingStepCreate, db: Session = Depends(get_db)):
    header = db.query(RoutingHeader).filter(RoutingHeader.id == routing_id).first()
    if not header:
        raise HTTPException(status_code=404, detail="Routing header not found")

    existing_seq = (
        db.query(RoutingStep)
        .filter(RoutingStep.routing_id == routing_id)
        .filter(RoutingStep.seq_no == payload.seq_no)
        .first()
    )
    if existing_seq:
        raise HTTPException(status_code=400, detail="RoutingStep.seq_no must be unique within the routing")

    step_code = _normalize_required_text(payload.step_code, "step_code")
    step_name = _normalize_required_text(payload.step_name, "step_name")
    department = payload.department.strip() if payload.department is not None else None
    if department == "":
        department = None

    row = RoutingStep(
        routing_id=routing_id,
        seq_no=payload.seq_no,
        step_code=step_code,
        step_name=step_name,
        department=department,
        is_required=payload.is_required,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/headers/{routing_id}", response_model=RoutingHeaderDetail)
def get_routing_header(routing_id: int, db: Session = Depends(get_db)):
    row = (
        db.query(RoutingHeader)
        .options(selectinload(RoutingHeader.steps))
        .filter(RoutingHeader.id == routing_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Routing header not found")
    row.steps.sort(key=lambda step: (step.seq_no, step.id))
    return row
