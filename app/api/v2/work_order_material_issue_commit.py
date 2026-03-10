from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import MaterialIssueEvent, StockLedger, WorkOrderBOMSnapshot
from app.api.v2.work_order_material_issue_preview import build_material_issue_preview_from_snapshot
from app.schemas.work_order_material_issue_commit import (
    WorkOrderMaterialIssueCommitRequest,
    WorkOrderMaterialIssueCommitResponse,
)


router = APIRouter(prefix="/v2/work-order", tags=["v2-work-order-material-issue-commit"])


@router.post("/material-issue-commit", response_model=WorkOrderMaterialIssueCommitResponse)
def work_order_material_issue_commit(
    payload: WorkOrderMaterialIssueCommitRequest,
    db: Session = Depends(get_db),
):
    snapshot = (
        db.query(WorkOrderBOMSnapshot)
        .filter(WorkOrderBOMSnapshot.id == payload.snapshot_id)
        .first()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot not found: id={payload.snapshot_id}")

    snapshot_status = str(snapshot.status).upper()
    if snapshot_status == "DRAFT":
        raise HTTPException(status_code=409, detail=f"Snapshot is DRAFT and cannot issue: id={payload.snapshot_id}")
    if snapshot_status == "VOID":
        raise HTTPException(status_code=409, detail=f"Snapshot is VOID and cannot issue: id={payload.snapshot_id}")
    if snapshot_status != "RELEASED":
        raise HTTPException(
            status_code=409,
            detail=f"Snapshot status {snapshot_status} cannot issue (only RELEASED allowed): id={payload.snapshot_id}",
        )

    issue_status = str(snapshot.issue_status or "PENDING").upper()
    if issue_status == "ISSUED":
        raise HTTPException(
            status_code=409,
            detail=f"Snapshot already ISSUED and cannot commit material issue: id={payload.snapshot_id}",
        )
    if issue_status != "PENDING":
        raise HTTPException(
            status_code=409,
            detail=f"Snapshot issue_status {issue_status} cannot commit material issue: id={payload.snapshot_id}",
        )

    preview = build_material_issue_preview_from_snapshot(snapshot=snapshot, db=db)
    issue_lines = preview["issue_lines"]

    try:
        issue_event = MaterialIssueEvent(
            snapshot_id=snapshot.id,
            work_order_no=snapshot.work_order_no,
            bom_version_id=snapshot.bom_version_id,
            org_id=payload.org_id,
            location_id=payload.location_id,
            issued_by=payload.issued_by,
            issued_at=datetime.utcnow(),
        )
        db.add(issue_event)
        db.flush()

        for line in issue_lines:
            db.add(
                StockLedger(
                    org_id=payload.org_id,
                    item_id=line["item_code"],
                    location_id=payload.location_id,
                    txn_type="ISSUE",
                    qty=float(line["required_qty"]),
                    uom=line["uom"],
                    ref_type="WORK_ORDER_BOM_SNAPSHOT",
                    ref_id=str(snapshot.id),
                    note=snapshot.work_order_no,
                    issue_event_id=issue_event.issue_event_id,
                    snapshot_id=snapshot.id,
                    work_order_no=snapshot.work_order_no,
                    occurred_at=datetime.utcnow(),
                )
            )

        snapshot.issue_status = "ISSUED"
        snapshot.issued_by = payload.issued_by
        snapshot.issued_at = datetime.utcnow()

        db.commit()
        db.refresh(snapshot)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Material issue commit failed and rolled back: id={payload.snapshot_id}")

    return {
        "snapshot_id": snapshot.id,
        "work_order_no": snapshot.work_order_no,
        "status": snapshot.status,
        "issue_status": snapshot.issue_status,
        "issued_by": snapshot.issued_by,
        "issued_at": snapshot.issued_at,
        "ledger_rows": [
            {
                "item_code": line["item_code"],
                "qty": line["required_qty"],
                "uom": line["uom"],
                "txn_type": "ISSUE",
            }
            for line in issue_lines
        ],
    }
