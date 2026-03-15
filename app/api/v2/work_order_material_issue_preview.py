from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import WorkOrderBOMSnapshot, WorkOrderBOMSnapshotLine
from app.schemas.work_order_material_issue_preview import (
    WorkOrderMaterialIssuePreviewRequest,
    WorkOrderMaterialIssuePreviewResponse,
)


router = APIRouter(prefix="/v2/work-order", tags=["v2-work-order-material-issue-preview"])


def _load_snapshot_issue_lines(snapshot_id: int, db: Session) -> list[dict]:
    detail_rows = (
        db.query(WorkOrderBOMSnapshotLine)
        .filter(WorkOrderBOMSnapshotLine.snapshot_id == snapshot_id)
        .order_by(WorkOrderBOMSnapshotLine.seq_no.asc(), WorkOrderBOMSnapshotLine.id.asc())
        .all()
    )
    return [
        {
            "item_code": row.item_code,
            "item_name": row.item_name,
            "required_qty": row.required_qty,
            "uom": row.uom,
        }
        for row in detail_rows
    ]


def build_material_issue_preview_from_snapshot(snapshot: WorkOrderBOMSnapshot, db: Session) -> dict:
    current_status = str(snapshot.status).upper()
    if current_status == "DRAFT":
        raise HTTPException(
            status_code=409,
            detail=f"Snapshot is DRAFT and cannot preview material issue: id={snapshot.id}",
        )
    if current_status == "VOID":
        raise HTTPException(
            status_code=409,
            detail=f"Snapshot is VOID and cannot preview material issue: id={snapshot.id}",
        )
    if current_status != "RELEASED":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Snapshot status {current_status} cannot preview material issue "
                f"(only RELEASED allowed): id={snapshot.id}"
            ),
        )

    issue_status = str(snapshot.issue_status or "PENDING").upper()
    if issue_status == "ISSUED":
        raise HTTPException(
            status_code=409,
            detail=f"Snapshot already ISSUED and cannot preview material issue: id={snapshot.id}",
        )
    if issue_status != "PENDING":
        raise HTTPException(
            status_code=409,
            detail=f"Snapshot issue_status {issue_status} cannot preview material issue: id={snapshot.id}",
        )

    if not snapshot.bom_version_id:
        raise HTTPException(status_code=409, detail=f"Snapshot missing bom_version_id: id={snapshot.id}")

    issue_lines = _load_snapshot_issue_lines(snapshot_id=snapshot.id, db=db)

    return {
        "snapshot_id": snapshot.id,
        "work_order_no": snapshot.work_order_no,
        "parent_system_item_code": snapshot.parent_system_item_code,
        "work_order_qty": snapshot.work_order_qty,
        "bom_version_id": snapshot.bom_version_id,
        "status": snapshot.status,
        "issue_lines": issue_lines,
    }


@router.post("/material-issue-preview", response_model=WorkOrderMaterialIssuePreviewResponse)
def work_order_material_issue_preview(
    payload: WorkOrderMaterialIssuePreviewRequest,
    db: Session = Depends(get_db),
):
    snapshot = (
        db.query(WorkOrderBOMSnapshot)
        .filter(WorkOrderBOMSnapshot.id == payload.snapshot_id)
        .first()
    )
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot not found: id={payload.snapshot_id}")

    return build_material_issue_preview_from_snapshot(snapshot=snapshot, db=db)
