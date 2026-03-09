from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import WorkOrderBOMSnapshot
from app.schemas.work_order_bom_release import (
    WorkOrderBOMReleaseRequest,
    WorkOrderBOMReleaseResponse,
)


router = APIRouter(prefix="/v2/work-order", tags=["v2-work-order-bom-release"])


@router.post("/bom-release", response_model=WorkOrderBOMReleaseResponse)
def work_order_bom_release(payload: WorkOrderBOMReleaseRequest, db: Session = Depends(get_db)):
    snapshot = (
        db.query(WorkOrderBOMSnapshot)
        .filter(WorkOrderBOMSnapshot.id == payload.snapshot_id)
        .first()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot not found: id={payload.snapshot_id}")

    current_status = str(snapshot.status).upper()
    if current_status == "RELEASED":
        raise HTTPException(status_code=409, detail=f"Snapshot already RELEASED: id={payload.snapshot_id}")
    if current_status == "VOID":
        raise HTTPException(status_code=409, detail=f"Snapshot is VOID and cannot be released: id={payload.snapshot_id}")
    if current_status != "DRAFT":
        raise HTTPException(
            status_code=409,
            detail=f"Snapshot status {current_status} cannot be released (only DRAFT allowed): id={payload.snapshot_id}",
        )

    snapshot.status = "RELEASED"
    snapshot.released_by = payload.released_by
    snapshot.released_at = datetime.utcnow()

    db.commit()
    db.refresh(snapshot)

    return {
        "snapshot_id": snapshot.id,
        "work_order_no": snapshot.work_order_no,
        "status": snapshot.status,
        "released_by": snapshot.released_by,
        "released_at": snapshot.released_at,
    }
