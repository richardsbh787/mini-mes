from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import MaterialIssueCorrectionEvent, MaterialIssueEvent, StockLedger, WorkOrderBOMSnapshot
from app.schemas.work_order_material_issue_correction_commit import (
    ALLOWED_CORRECTION_REASON_CODES,
    WorkOrderMaterialIssueCorrectionCommitRequest,
    WorkOrderMaterialIssueCorrectionCommitResponse,
)


router = APIRouter(prefix="/v2/work-order", tags=["v2-work-order-material-issue-correction-commit"])


@router.post("/material-issue-correction-commit", response_model=WorkOrderMaterialIssueCorrectionCommitResponse)
def work_order_material_issue_correction_commit(
    payload: WorkOrderMaterialIssueCorrectionCommitRequest,
    db: Session = Depends(get_db),
):
    if payload.reason_code not in ALLOWED_CORRECTION_REASON_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported correction reason_code: {payload.reason_code}",
        )
    if payload.reason_code == "OTHER" and not payload.reason_note:
        raise HTTPException(
            status_code=400,
            detail="reason_note is required when reason_code=OTHER",
        )

    issue_event = (
        db.query(MaterialIssueEvent)
        .filter(MaterialIssueEvent.issue_event_id == payload.original_issue_event_id)
        .first()
    )
    if not issue_event:
        raise HTTPException(
            status_code=404,
            detail=f"Issue event not found: issue_event_id={payload.original_issue_event_id}",
        )

    snapshot = (
        db.query(WorkOrderBOMSnapshot)
        .filter(WorkOrderBOMSnapshot.id == issue_event.snapshot_id)
        .first()
    )
    if not snapshot:
        raise HTTPException(
            status_code=404,
            detail=f"Snapshot not found for issue_event_id={payload.original_issue_event_id}",
        )

    existing_correction = (
        db.query(MaterialIssueCorrectionEvent)
        .filter(MaterialIssueCorrectionEvent.original_issue_event_id == payload.original_issue_event_id)
        .first()
    )
    if existing_correction:
        raise HTTPException(
            status_code=409,
            detail=f"Issue event already corrected: issue_event_id={payload.original_issue_event_id}",
        )

    original_rows = (
        db.query(StockLedger)
        .filter(StockLedger.issue_event_id == payload.original_issue_event_id)
        .order_by(StockLedger.id.asc())
        .all()
    )
    if not original_rows:
        raise HTTPException(
            status_code=409,
            detail=f"Issue event has no ledger rows to correct: issue_event_id={payload.original_issue_event_id}",
        )

    try:
        correction_event = MaterialIssueCorrectionEvent(
            original_issue_event_id=issue_event.issue_event_id,
            snapshot_id=issue_event.snapshot_id,
            work_order_no=issue_event.work_order_no,
            org_id=issue_event.org_id,
            location_id=issue_event.location_id,
            reason_code=payload.reason_code,
            reason_note=payload.reason_note,
            corrected_by=payload.corrected_by,
            corrected_at=datetime.utcnow(),
        )
        db.add(correction_event)
        db.flush()

        for row in original_rows:
            db.add(
                StockLedger(
                    org_id=row.org_id,
                    item_id=row.item_id,
                    location_id=row.location_id,
                    txn_type="RECEIPT",
                    qty=float(row.qty),
                    uom=row.uom,
                    ref_type="MATERIAL_ISSUE_CORRECTION",
                    ref_id=str(correction_event.correction_event_id),
                    note=row.note,
                    correction_event_id=correction_event.correction_event_id,
                    snapshot_id=row.snapshot_id,
                    work_order_no=row.work_order_no,
                    occurred_at=datetime.utcnow(),
                )
            )

        db.commit()
        db.refresh(correction_event)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=(
                "Material issue correction commit failed and rolled back: "
                f"issue_event_id={payload.original_issue_event_id}"
            ),
        )

    return {
        "correction_event_id": correction_event.correction_event_id,
        "original_issue_event_id": correction_event.original_issue_event_id,
        "snapshot_id": correction_event.snapshot_id,
        "work_order_no": correction_event.work_order_no,
        "corrected_by": correction_event.corrected_by,
        "corrected_at": correction_event.corrected_at,
        "ledger_rows": [
            {
                "item_code": row.item_id,
                "qty": row.qty,
                "uom": row.uom,
                "txn_type": "RECEIPT",
            }
            for row in original_rows
        ],
    }
