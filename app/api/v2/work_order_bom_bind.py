from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import WorkOrderBOMSnapshot
from app.api.v2.work_order_bom_preview import build_work_order_bom_preview
from app.schemas.work_order_bom_bind import (
    WorkOrderBOMBindRequest,
    WorkOrderBOMBindResponse,
)


router = APIRouter(prefix="/v2/work-order", tags=["v2-work-order-bom-bind"])


@router.post("/bom-bind", response_model=WorkOrderBOMBindResponse)
def work_order_bom_bind(payload: WorkOrderBOMBindRequest, db: Session = Depends(get_db)):
    exists = (
        db.query(WorkOrderBOMSnapshot)
        .filter(WorkOrderBOMSnapshot.work_order_no == payload.work_order_no)
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=409,
            detail=f"Snapshot already exists for work_order_no={payload.work_order_no}",
        )

    preview = build_work_order_bom_preview(
        db=db,
        parent_system_item_code=payload.parent_system_item_code,
        work_order_qty=payload.work_order_qty,
        version_id=payload.version_id,
    )

    snapshot = WorkOrderBOMSnapshot(
        work_order_no=payload.work_order_no,
        parent_system_item_code=payload.parent_system_item_code,
        work_order_qty=payload.work_order_qty,
        bom_version_id=preview["version_id"],
        created_by=payload.created_by,
    )
    db.add(snapshot)
    try:
        db.commit()
        db.refresh(snapshot)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Snapshot already exists for work_order_no={payload.work_order_no}",
        )

    return {
        "snapshot_id": snapshot.id,
        "work_order_no": snapshot.work_order_no,
        "parent_system_item_code": snapshot.parent_system_item_code,
        "work_order_qty": snapshot.work_order_qty,
        "version_id": snapshot.bom_version_id,
        "flat_materials": preview["flat_materials"],
        "tree": preview["tree"],
    }
