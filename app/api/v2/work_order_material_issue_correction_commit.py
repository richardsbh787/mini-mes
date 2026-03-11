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


def validate_correction_posting_guard(
    payload: WorkOrderMaterialIssueCorrectionCommitRequest,
    issue_event: MaterialIssueEvent,
    original_rows: list[StockLedger],
) -> tuple[str, str]:
    reason_code = (payload.reason_code or "").strip().upper()
    corrected_by = (payload.corrected_by or "").strip()

    if not reason_code:
        raise HTTPException(status_code=400, detail="reason_code is required")
    if not corrected_by:
        raise HTTPException(status_code=400, detail="corrected_by is required")
    if reason_code not in ALLOWED_CORRECTION_REASON_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported correction reason_code: {payload.reason_code}",
        )
    if reason_code == "OTHER" and not payload.reason_note:
        raise HTTPException(
            status_code=400,
            detail="reason_note is required when reason_code=OTHER",
        )
    if not issue_event.snapshot_id or not issue_event.work_order_no or not issue_event.bom_version_id:
        raise HTTPException(
            status_code=409,
            detail=f"Issue event is not eligible for correction: issue_event_id={payload.original_issue_event_id}",
        )
    if not issue_event.org_id or not issue_event.org_id.strip():
        raise HTTPException(
            status_code=409,
            detail=f"Correction context mismatch with original trace: issue_event_id={payload.original_issue_event_id}",
        )
    if not issue_event.location_id or not issue_event.location_id.strip():
        raise HTTPException(
            status_code=409,
            detail=f"Correction context mismatch with original trace: issue_event_id={payload.original_issue_event_id}",
        )

    eligible_original_qty = 0.0
    correction_qty = 0.0
    for row in original_rows:
        row_qty = float(row.qty)
        if row.issue_event_id != issue_event.issue_event_id:
            raise HTTPException(
                status_code=409,
                detail=f"Issue event is not eligible for correction: issue_event_id={payload.original_issue_event_id}",
            )
        if row.correction_event_id is not None or row.txn_type != "ISSUE":
            raise HTTPException(
                status_code=409,
                detail=f"Issue event is not eligible for correction: issue_event_id={payload.original_issue_event_id}",
            )
        if row_qty <= 0:
            raise HTTPException(
                status_code=409,
                detail=f"Issue event is not eligible for correction: issue_event_id={payload.original_issue_event_id}",
            )
        if row.org_id != issue_event.org_id or row.location_id != issue_event.location_id:
            raise HTTPException(
                status_code=409,
                detail=f"Correction context mismatch with original trace: issue_event_id={payload.original_issue_event_id}",
            )
        if not row.item_id or not str(row.item_id).strip():
            raise HTTPException(
                status_code=409,
                detail=f"Correction context mismatch with original trace: issue_event_id={payload.original_issue_event_id}",
            )
        if not row.uom or not str(row.uom).strip():
            raise HTTPException(
                status_code=409,
                detail=f"Correction context mismatch with original trace: issue_event_id={payload.original_issue_event_id}",
            )
        eligible_original_qty += row_qty
        correction_qty += row_qty

    if correction_qty <= 0:
        raise HTTPException(
            status_code=409,
            detail=f"Issue event is not eligible for correction: issue_event_id={payload.original_issue_event_id}",
        )
    if correction_qty > eligible_original_qty:
        raise HTTPException(
            status_code=409,
            detail=f"Correction qty exceeds original issued qty: issue_event_id={payload.original_issue_event_id}",
        )

    return reason_code, corrected_by


@router.post("/material-issue-correction-commit", response_model=WorkOrderMaterialIssueCorrectionCommitResponse)
def work_order_material_issue_correction_commit(
    payload: WorkOrderMaterialIssueCorrectionCommitRequest,
    db: Session = Depends(get_db),
):
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

    reason_code, corrected_by = validate_correction_posting_guard(
        payload=payload,
        issue_event=issue_event,
        original_rows=original_rows,
    )

    try:
        correction_event = MaterialIssueCorrectionEvent(
            original_issue_event_id=issue_event.issue_event_id,
            snapshot_id=issue_event.snapshot_id,
            work_order_no=issue_event.work_order_no,
            org_id=issue_event.org_id,
            location_id=issue_event.location_id,
            reason_code=reason_code,
            reason_note=payload.reason_note,
            corrected_by=corrected_by,
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
                    uom=str(row.uom).strip(),
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
