from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import MaterialIssueCorrectionEvent
from app.schemas.work_order_material_issue_correction_query import (
    WorkOrderMaterialIssueCorrectionQueryResponse,
)


router = APIRouter(prefix="/v2", tags=["v2-material-issue-correction-query"])
DEFAULT_CORRECTION_LIST_LIMIT = 100
MAX_CORRECTION_LIST_LIMIT = 500


def serialize_correction_event(
    correction_event: MaterialIssueCorrectionEvent,
) -> dict[str, object]:
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


@router.get(
    "/material-issue-corrections",
    response_model=list[WorkOrderMaterialIssueCorrectionQueryResponse],
)
def list_material_issue_corrections(
    work_order_no: str | None = None,
    reason_code: str | None = None,
    corrected_by: str | None = None,
    limit: int = DEFAULT_CORRECTION_LIST_LIMIT,
    db: Session = Depends(get_db),
):
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be > 0")
    if limit > MAX_CORRECTION_LIST_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"limit must be <= {MAX_CORRECTION_LIST_LIMIT}",
        )

    query = db.query(MaterialIssueCorrectionEvent)

    if work_order_no is not None:
        normalized_work_order_no = work_order_no.strip()
        if normalized_work_order_no:
            query = query.filter(MaterialIssueCorrectionEvent.work_order_no == normalized_work_order_no)

    if reason_code is not None:
        normalized_reason_code = reason_code.strip().upper()
        if normalized_reason_code:
            query = query.filter(MaterialIssueCorrectionEvent.reason_code == normalized_reason_code)

    if corrected_by is not None:
        normalized_corrected_by = corrected_by.strip()
        if normalized_corrected_by:
            query = query.filter(MaterialIssueCorrectionEvent.corrected_by == normalized_corrected_by)

    correction_events = (
        query.order_by(MaterialIssueCorrectionEvent.correction_event_id.desc())
        .limit(limit)
        .all()
    )
    return [serialize_correction_event(correction_event) for correction_event in correction_events]


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

    return serialize_correction_event(correction_event)
