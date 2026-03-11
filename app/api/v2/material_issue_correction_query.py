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
CORRECTION_QUERY_FIELD_NAMES = (
    "correction_event_id",
    "original_issue_event_id",
    "snapshot_id",
    "work_order_no",
    "reason_code",
    "reason_note",
    "corrected_by",
    "corrected_at",
)


def normalize_correction_reason_code_filter(reason_code: str | None) -> str | None:
    if reason_code is None:
        return None
    normalized_reason_code = reason_code.strip().upper()
    return normalized_reason_code or None


def apply_correction_list_default_order(query):
    return query.order_by(MaterialIssueCorrectionEvent.correction_event_id.desc())


def serialize_correction_event(
    correction_event: MaterialIssueCorrectionEvent,
) -> dict[str, object]:
    return {field_name: getattr(correction_event, field_name) for field_name in CORRECTION_QUERY_FIELD_NAMES}


@router.get(
    "/material-issue-corrections",
    response_model=list[WorkOrderMaterialIssueCorrectionQueryResponse],
    summary="List correction governance records",
    description=(
        "Read-only minimal governance list surface for material issue corrections. "
        "Supports only the fixed correction-event filters on this endpoint and is intended "
        "for minimal manual lookup of correction records. "
        "Not a reporting, analytics, export, ledger-detail, or approval-workflow API."
    ),
    response_description="Read-only list of minimal correction governance records.",
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

    normalized_reason_code = normalize_correction_reason_code_filter(reason_code)
    if normalized_reason_code:
        query = query.filter(MaterialIssueCorrectionEvent.reason_code == normalized_reason_code)

    if corrected_by is not None:
        normalized_corrected_by = corrected_by.strip()
        if normalized_corrected_by:
            query = query.filter(MaterialIssueCorrectionEvent.corrected_by == normalized_corrected_by)

    correction_events = apply_correction_list_default_order(query).limit(limit).all()
    return [serialize_correction_event(correction_event) for correction_event in correction_events]


@router.get(
    "/material-issue-correction/{original_issue_event_id}",
    response_model=WorkOrderMaterialIssueCorrectionQueryResponse,
    summary="Get correction governance record by original issue event",
    description=(
        "Read-only minimal governance lookup for checking whether a correction exists for "
        "a specific original material issue event and for reading the fixed correction "
        "governance fields exposed by this API. "
        "Not a ledger-detail, correction-line, approval-state, inventory-summary, "
        "reporting, analytics, or export API."
    ),
    response_description="Read-only minimal correction governance record for the original issue event.",
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
