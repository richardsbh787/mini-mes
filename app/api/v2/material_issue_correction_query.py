from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import MaterialIssueCorrectionEvent
from app.schemas.work_order_material_issue_correction_query import (
    WorkOrderMaterialIssueCorrectionQueryResponse,
)


router = APIRouter(prefix="/v2", tags=["v2-material-issue-correction-query"])


@router.get(
    "/material-issue-correction/{original_issue_event_id}",
    response_model=WorkOrderMaterialIssueCorrectionQueryResponse,
)
def get_material_issue_correction(
    original_issue_event_id: int,
    db: Session = Depends(get_db),
):
    if original_issue_event_id <= 0:
        raise HTTPException(status_code=400, detail="original_issue_event_id must be > 0")

    correction_event = (
        db.query(MaterialIssueCorrectionEvent)
        .filter(MaterialIssueCorrectionEvent.original_issue_event_id == original_issue_event_id)
        .first()
    )
    if not correction_event:
        raise HTTPException(
            status_code=404,
            detail=f"Correction not found for original_issue_event_id={original_issue_event_id}",
        )

    return {
        "correction_event_id": correction_event.correction_event_id,
        "original_issue_event_id": correction_event.original_issue_event_id,
        "snapshot_id": correction_event.snapshot_id,
        "work_order_no": correction_event.work_order_no,
        "reason_code": correction_event.reason_code,
        "reason_note": correction_event.reason_note,
        "corrected_by": correction_event.corrected_by,
        "corrected_at": correction_event.corrected_at,
    }
