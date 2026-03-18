from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.stock_ledger_rm_issue import RmIssueLedgerPostRequest, StockLedgerRmIssueResponse
from models import MaterialIssueEvent, RawMaterial, StockLedger, WorkOrder, WorkOrderBOMSnapshot, WorkOrderBOMSnapshotLine


SOURCE_EVENT_TYPE = "RM_ISSUE"
MOVEMENT_TYPE = "OUT"
STOCK_BUCKET = "RAW_MATERIAL"
LEGACY_TXN_TYPE = "ISSUE"
SUCCESS_ISSUE_STATUS = "ISSUED"


def post_rm_issue_stock_ledger(
    db: Session,
    *,
    issue_event_id: int,
    payload: RmIssueLedgerPostRequest,
) -> list[StockLedgerRmIssueResponse]:
    normalized = _validate_post_input(payload)

    issue_event = db.query(MaterialIssueEvent).filter(MaterialIssueEvent.issue_event_id == issue_event_id).first()
    if issue_event is None:
        raise HTTPException(status_code=404, detail=f"RM issue event not found: id={issue_event_id}")

    snapshot = db.query(WorkOrderBOMSnapshot).filter(WorkOrderBOMSnapshot.id == issue_event.snapshot_id).first()
    if snapshot is None:
        raise HTTPException(
            status_code=409,
            detail=f"RM issue snapshot could not be resolved for stock ledger posting: issue_event_id={issue_event.issue_event_id}",
        )

    issue_status = _status(snapshot.issue_status)
    if issue_status != SUCCESS_ISSUE_STATUS:
        raise HTTPException(
            status_code=409,
            detail=(
                "RM issue stock ledger posting requires committed issue truth: "
                f"issue_event_id={issue_event.issue_event_id}, issue_status={snapshot.issue_status}"
            ),
        )

    issue_lines = _load_issue_lines(snapshot_id=snapshot.id, db=db)
    if not issue_lines:
        raise HTTPException(
            status_code=409,
            detail=f"RM issue has no persisted issue lines for stock ledger posting: issue_event_id={issue_event.issue_event_id}",
        )

    work_order = _resolve_work_order(db=db, issue_event=issue_event, snapshot=snapshot)

    posted_at = datetime.utcnow()
    created_rows: list[StockLedger] = []

    for line in issue_lines:
        _guard_duplicate_rm_issue_line_ledger_post(
            db=db,
            issue_event_id=issue_event.issue_event_id,
            issue_line_id=line.id,
        )
        item_master = _resolve_inventory_subject(line=line, db=db, issue_event=issue_event)
        base_qty, base_uom = _resolve_base_quantity_and_uom(
            item_master=item_master,
            txn_qty=float(line.required_qty),
            txn_uom=str(line.uom or "").strip().upper(),
        )

        item_code = str(item_master.material_code).strip()
        row = StockLedger(
            org_id=issue_event.org_id,
            ledger_no=_format_pending_ledger_no(issue_event_id=issue_event.issue_event_id, issue_line_id=line.id),
            item_id=item_code,
            item_code=item_code,
            location_id=issue_event.location_id,
            txn_type=LEGACY_TXN_TYPE,
            movement_type=MOVEMENT_TYPE,
            stock_bucket=STOCK_BUCKET,
            qty=0 - base_qty,
            uom=base_uom,
            txn_qty=float(line.required_qty),
            txn_uom=str(line.uom or "").strip().upper(),
            base_qty=base_qty,
            base_uom=base_uom,
            ref_type=SOURCE_EVENT_TYPE,
            ref_id=str(issue_event.issue_event_id),
            note=normalized["remark"],
            source_event_type=SOURCE_EVENT_TYPE,
            source_event_id=issue_event.issue_event_id,
            source_event_line_id=line.id,
            work_order_id=work_order.id,
            sales_order_id=work_order.sales_order_id,
            work_order_no=work_order.work_order_no,
            issue_event_id=issue_event.issue_event_id,
            snapshot_id=snapshot.id,
            posted_by=normalized["posted_by"],
            remark=normalized["remark"],
            posted_at=posted_at,
            occurred_at=posted_at,
        )
        db.add(row)
        created_rows.append(row)

    try:
        db.flush()
        for row in created_rows:
            row.ledger_no = _format_ledger_no(row.id)
            db.add(row)
        db.commit()
        for row in created_rows:
            db.refresh(row)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"RM issue stock ledger posting failed and rolled back: issue_event_id={issue_event.issue_event_id}",
        )

    return [_to_response(row) for row in created_rows]


def list_rm_issue_stock_ledger(
    db: Session,
    *,
    issue_event_id: int,
) -> list[StockLedgerRmIssueResponse]:
    rows = (
        db.query(StockLedger)
        .filter(StockLedger.source_event_type == SOURCE_EVENT_TYPE)
        .filter(StockLedger.source_event_id == issue_event_id)
        .order_by(StockLedger.source_event_line_id.asc(), StockLedger.id.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"RM issue stock ledger not found: issue_event_id={issue_event_id}")
    return [_to_response(row) for row in rows]


def _validate_post_input(payload: RmIssueLedgerPostRequest) -> dict[str, str | None]:
    normalized = {
        "posted_by": str(payload.posted_by or "").strip(),
        "remark": _normalize_optional_text(payload.remark),
    }
    if not normalized["posted_by"]:
        raise HTTPException(status_code=409, detail="Invalid posted_by for RM issue stock ledger: posted_by is required")
    return normalized


def _load_issue_lines(*, snapshot_id: int, db: Session) -> list[WorkOrderBOMSnapshotLine]:
    return (
        db.query(WorkOrderBOMSnapshotLine)
        .filter(WorkOrderBOMSnapshotLine.snapshot_id == snapshot_id)
        .order_by(WorkOrderBOMSnapshotLine.seq_no.asc(), WorkOrderBOMSnapshotLine.id.asc())
        .all()
    )


def _resolve_work_order(*, db: Session, issue_event: MaterialIssueEvent, snapshot: WorkOrderBOMSnapshot) -> WorkOrder:
    work_order_no = str(issue_event.work_order_no or snapshot.work_order_no or "").strip()
    work_order = db.query(WorkOrder).filter(WorkOrder.work_order_no == work_order_no).first()
    if work_order is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "RM issue work order could not be resolved for stock ledger posting: "
                f"issue_event_id={issue_event.issue_event_id}, work_order_no={work_order_no}"
            ),
        )
    return work_order


def _guard_duplicate_rm_issue_line_ledger_post(*, db: Session, issue_event_id: int, issue_line_id: int) -> None:
    existing = (
        db.query(StockLedger)
        .filter(StockLedger.source_event_type == SOURCE_EVENT_TYPE)
        .filter(StockLedger.source_event_id == issue_event_id)
        .filter(StockLedger.source_event_line_id == issue_line_id)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Duplicate RM issue stock ledger posting is not allowed: "
                f"issue_event_id={issue_event_id}, source_event_line_id={issue_line_id}"
            ),
        )


def _resolve_inventory_subject(
    *,
    line: WorkOrderBOMSnapshotLine,
    db: Session,
    issue_event: MaterialIssueEvent,
) -> RawMaterial:
    line_material_code = str(line.item_code or "").strip()
    if not line_material_code:
        raise HTTPException(
            status_code=409,
            detail=(
                "RM issue item resolution failed through rm_issue_event -> rm_issue_line -> material_code -> "
                "RawMaterial.material_code: "
                f"issue_event_id={issue_event.issue_event_id}, source_event_line_id={line.id}"
            ),
        )

    item_master = db.query(RawMaterial).filter(RawMaterial.material_code == line_material_code).first()
    if item_master is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "RM issue item resolution failed through rm_issue_event -> rm_issue_line -> material_code -> "
                "RawMaterial.material_code: "
                f"issue_event_id={issue_event.issue_event_id}, source_event_line_id={line.id}, material_code={line_material_code}"
            ),
        )

    return item_master


def _resolve_base_quantity_and_uom(*, item_master: RawMaterial, txn_qty: float, txn_uom: str) -> tuple[float, str]:
    base_uom = str(item_master.unit or "").strip().upper()
    if not base_uom:
        raise HTTPException(
            status_code=409,
            detail=f"RM issue stock ledger base_uom is missing for item_code={item_master.material_code}",
        )

    if txn_uom == base_uom:
        return txn_qty, base_uom

    conversion_type = str(item_master.conversion_type or "").strip().upper()
    if conversion_type != "STANDARD":
        raise HTTPException(
            status_code=409,
            detail=(
                "RM issue stock ledger conversion could not be resolved through SF-01: "
                f"item_code={item_master.material_code}, conversion_type={item_master.conversion_type}"
            ),
        )

    ratio = float(item_master.standard_conversion_ratio or 0)
    if ratio <= 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "RM issue stock ledger conversion could not be resolved through SF-01: "
                f"item_code={item_master.material_code}, standard_conversion_ratio={item_master.standard_conversion_ratio}"
            ),
        )

    return txn_qty * ratio, base_uom


def _format_ledger_no(row_id: int | None) -> str:
    if row_id is None:
        raise HTTPException(status_code=500, detail="RM issue stock ledger number could not be assigned")
    return f"SLED-{row_id:06d}"


def _format_pending_ledger_no(*, issue_event_id: int, issue_line_id: int) -> str:
    return f"PENDING-RMI-{issue_event_id}-{issue_line_id}"


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _status(value: str | None) -> str:
    return str(value or "").strip().upper()


def _to_response(row: StockLedger) -> StockLedgerRmIssueResponse:
    return StockLedgerRmIssueResponse(
        id=row.id,
        ledger_no=str(row.ledger_no or ""),
        source_event_type=str(row.source_event_type or ""),
        source_event_id=int(row.source_event_id),
        source_event_line_id=int(row.source_event_line_id),
        work_order_id=int(row.work_order_id),
        sales_order_id=row.sales_order_id,
        item_code=str(row.item_code or row.item_id or ""),
        movement_type=str(row.movement_type or ""),
        stock_bucket=str(row.stock_bucket or ""),
        txn_qty=float(row.txn_qty if row.txn_qty is not None else abs(row.qty)),
        txn_uom=str(row.txn_uom or row.uom or ""),
        base_qty=float(row.base_qty if row.base_qty is not None else abs(row.qty)),
        base_uom=str(row.base_uom or row.uom or ""),
        posted_at=row.posted_at or row.occurred_at,
        posted_by=str(row.posted_by or ""),
        remark=row.remark,
    )
