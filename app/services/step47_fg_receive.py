from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.step47_fg_receive import (
    FgReceiveAttemptRead,
    FgReceiveEvidenceSnapshotRead,
    FgReceiveFinalTruthRead,
    FgReceiveResolutionDetailRead,
    FgReceiveResolutionListItem,
    FgReceiveResolutionOutcome,
    FgReceiveResolutionSummaryRead,
    FgReceiveRuntimeOutcomeRead,
    FgReceiveSourceEventContextRead,
    FgReceiveStep47ExecuteRequest,
    FgReceiveStep47ExecuteResponse,
)
from models import (
    FgReceiveEventTruth,
    FgReceiveLocationEvidenceSnapshot,
    FgReceiveLocationResolutionAttempt,
    LabelLocationMapping,
    LocationLabel,
    PhysicalLocation,
    Product,
    RawMaterial,
    StockLedger,
    WorkOrder,
    WorkOrderFgReceive,
)


SOURCE_EVENT_TYPE = "FG_RECEIVE"
MOVEMENT_TYPE = "IN"
STOCK_BUCKET = "FINISHED_GOODS"
LEGACY_TXN_TYPE = "RECEIPT"
FG_RECEIVE_STEP47_ADMITTED_SOURCE_ACTIVE = False
FG_RECEIVE_STEP47_RUNTIME_PRODUCTION_USE_AUTHORIZED = False


@dataclass(frozen=True)
class _ResolutionResult:
    outcome_class: FgReceiveResolutionOutcome
    source_label_token: str | None
    resolved_location_code: str | None
    failure_reason: str | None
    label: LocationLabel | None
    mapping: LabelLocationMapping | None
    location: PhysicalLocation | None


def execute_fg_receive_step47(
    db: Session,
    *,
    fg_receive_id: int,
    payload: FgReceiveStep47ExecuteRequest,
) -> FgReceiveStep47ExecuteResponse:
    normalized_executed_by = str(payload.executed_by or "").strip()
    if not normalized_executed_by:
        raise HTTPException(status_code=422, detail="executed_by is required")
    if not FG_RECEIVE_STEP47_ADMITTED_SOURCE_ACTIVE:
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive Step 47 implementation exists but execution remains blocked: "
                "admitted-source activation remains inactive; "
                "runtime production use remains unauthorized"
            ),
        )

    fg_receive = db.query(WorkOrderFgReceive).filter(WorkOrderFgReceive.id == fg_receive_id).first()
    if fg_receive is None:
        raise HTTPException(status_code=404, detail=f"FG receive not found: id={fg_receive_id}")

    _guard_no_existing_final_truth(db=db, fg_receive_id=fg_receive.id)
    _guard_no_existing_position_write(db=db, fg_receive_id=fg_receive.id)

    now = datetime.utcnow()
    resolution = _resolve_event_time_location(db=db, fg_receive=fg_receive)
    attempt = FgReceiveLocationResolutionAttempt(
        fg_receive_id=fg_receive.id,
        source_label_token=resolution.source_label_token,
        outcome_class=resolution.outcome_class.value,
        resolved_location_code=resolution.resolved_location_code,
        failure_reason=resolution.failure_reason,
        attempted_at=now,
        completed_at=now,
        attempted_by=normalized_executed_by,
    )
    db.add(attempt)
    db.flush()

    evidence_snapshot = _create_evidence_snapshot(
        db=db,
        fg_receive=fg_receive,
        resolution=resolution,
        now=now,
    )
    if evidence_snapshot is not None:
        attempt.evidence_snapshot_id = evidence_snapshot.id
        db.add(attempt)

    final_truth = None
    stock_ledger = None
    if resolution.outcome_class == FgReceiveResolutionOutcome.SUCCESS:
        if evidence_snapshot is None or resolution.resolved_location_code is None:
            raise HTTPException(status_code=409, detail="FG receive Step 47 success requires immutable evidence snapshot and bound location")
        final_truth = FgReceiveEventTruth(
            fg_receive_id=fg_receive.id,
            bound_location_code=resolution.resolved_location_code,
            bound_from_resolution_attempt_id=attempt.id,
            location_evidence_snapshot_ref=evidence_snapshot.id,
            location_bound_at=now,
        )
        db.add(final_truth)
        db.flush()
        stock_ledger = _create_legal_position_row(
            db=db,
            fg_receive=fg_receive,
            bound_location_code=final_truth.bound_location_code,
            posted_by=normalized_executed_by,
            occurred_at=now,
            remark=payload.remark,
        )
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"FG receive Step 47 execution failed and rolled back: fg_receive_id={fg_receive_id}")

    db.refresh(attempt)
    if evidence_snapshot is not None:
        db.refresh(evidence_snapshot)
    if final_truth is not None:
        db.refresh(final_truth)
    if stock_ledger is not None:
        db.refresh(stock_ledger)

    return FgReceiveStep47ExecuteResponse(
        fg_receive_id=fg_receive.id,
        attempt_id=int(attempt.id),
        outcome_class=FgReceiveResolutionOutcome(str(attempt.outcome_class)),
        evidence_snapshot_id=evidence_snapshot.id if evidence_snapshot is not None else None,
        final_truth_id=final_truth.id if final_truth is not None else None,
        stock_ledger_id=stock_ledger.id if stock_ledger is not None else None,
        bound_location_code=final_truth.bound_location_code if final_truth is not None else None,
        admitted_source_activation_active=FG_RECEIVE_STEP47_ADMITTED_SOURCE_ACTIVE,
        runtime_production_use_authorized=FG_RECEIVE_STEP47_RUNTIME_PRODUCTION_USE_AUTHORIZED,
    )


def list_fg_receive_step47_resolution_cases(
    db: Session,
    *,
    outcome_class: str | None = None,
    has_final_truth: bool | None = None,
    has_evidence_snapshot: bool | None = None,
) -> list[FgReceiveResolutionListItem]:
    normalized_outcome = _normalize_optional_text(outcome_class, upper=True)
    if normalized_outcome is not None and normalized_outcome not in {outcome.value for outcome in FgReceiveResolutionOutcome}:
        raise HTTPException(status_code=422, detail="Invalid outcome_class for FG receive Step 47 list")

    fg_receives = db.query(WorkOrderFgReceive).order_by(WorkOrderFgReceive.received_at.desc(), WorkOrderFgReceive.id.desc()).all()
    items: list[FgReceiveResolutionListItem] = []
    for fg_receive in fg_receives:
        attempts = _list_attempt_rows(db=db, fg_receive_id=fg_receive.id)
        latest_attempt = attempts[0] if attempts else None
        evidence_rows = _list_evidence_rows(db=db, fg_receive_id=fg_receive.id)
        final_truth = _get_final_truth(db=db, fg_receive_id=fg_receive.id)
        item = FgReceiveResolutionListItem(
            fg_receive_id=int(fg_receive.id),
            fg_receive_no=str(fg_receive.fg_receive_no or ""),
            work_order_id=int(fg_receive.work_order_id),
            latest_outcome_class=FgReceiveResolutionOutcome(str(latest_attempt.outcome_class)) if latest_attempt is not None else None,
            has_final_truth=final_truth is not None,
            has_evidence_snapshot=bool(evidence_rows),
            has_attempt_linkage=latest_attempt is not None,
            has_evidence_linkage=latest_attempt is not None and latest_attempt.evidence_snapshot_id is not None,
            has_final_truth_linkage=final_truth is not None,
            fg_receive_received_at=fg_receive.received_at,
            attempt_attempted_at=latest_attempt.attempted_at if latest_attempt is not None else None,
            evidence_captured_at=evidence_rows[0].captured_at if evidence_rows else None,
            final_truth_bound_at=final_truth.location_bound_at if final_truth is not None else None,
        )
        if normalized_outcome is not None and (item.latest_outcome_class is None or item.latest_outcome_class.value != normalized_outcome):
            continue
        if has_final_truth is not None and item.has_final_truth != has_final_truth:
            continue
        if has_evidence_snapshot is not None and item.has_evidence_snapshot != has_evidence_snapshot:
            continue
        items.append(item)
    return items


def get_fg_receive_step47_resolution_detail(
    db: Session,
    *,
    fg_receive_id: int,
) -> FgReceiveResolutionDetailRead:
    fg_receive = db.query(WorkOrderFgReceive).filter(WorkOrderFgReceive.id == fg_receive_id).first()
    if fg_receive is None:
        raise HTTPException(status_code=404, detail=f"FG receive not found: id={fg_receive_id}")

    attempts = _list_attempt_rows(db=db, fg_receive_id=fg_receive.id)
    evidence_rows = _list_evidence_rows(db=db, fg_receive_id=fg_receive.id)
    final_truth = _get_final_truth(db=db, fg_receive_id=fg_receive.id)
    latest_attempt = attempts[0] if attempts else None

    return FgReceiveResolutionDetailRead(
        source_event_context=FgReceiveSourceEventContextRead(
            fg_receive_id=int(fg_receive.id),
            fg_receive_no=str(fg_receive.fg_receive_no or ""),
            work_order_id=int(fg_receive.work_order_id),
            wip_transfer_id=int(fg_receive.wip_transfer_id),
            routing_snapshot_id=int(fg_receive.routing_snapshot_id),
            fg_handling_unit_type=str(fg_receive.fg_handling_unit_type or ""),
            fg_handling_unit_label=fg_receive.fg_handling_unit_label,
            txn_qty=float(fg_receive.txn_qty),
            txn_uom=str(fg_receive.txn_uom or ""),
            receive_status=str(fg_receive.receive_status or ""),
            received_at=fg_receive.received_at,
            received_by=str(fg_receive.received_by or ""),
            remark=fg_receive.remark,
        ),
        attempt_history=[_to_attempt_read(row) for row in attempts],
        evidence_snapshots=[_to_evidence_read(row) for row in evidence_rows],
        runtime_outcome=FgReceiveRuntimeOutcomeRead(
            latest_outcome_class=FgReceiveResolutionOutcome(str(latest_attempt.outcome_class)) if latest_attempt is not None else None,
            latest_attempt_id=int(latest_attempt.id) if latest_attempt is not None else None,
            latest_attempted_at=latest_attempt.attempted_at if latest_attempt is not None else None,
            latest_completed_at=latest_attempt.completed_at if latest_attempt is not None else None,
            latest_failure_reason=latest_attempt.failure_reason if latest_attempt is not None else None,
        ),
        final_event_truth=_to_final_truth_read(final_truth) if final_truth is not None else None,
    )


def summarize_fg_receive_step47_resolution(db: Session) -> FgReceiveResolutionSummaryRead:
    rows = list_fg_receive_step47_resolution_cases(db=db)
    return FgReceiveResolutionSummaryRead(
        success_count=sum(1 for row in rows if row.latest_outcome_class == FgReceiveResolutionOutcome.SUCCESS),
        failed_count=sum(1 for row in rows if row.latest_outcome_class == FgReceiveResolutionOutcome.FAILED),
        ambiguous_count=sum(1 for row in rows if row.latest_outcome_class == FgReceiveResolutionOutcome.AMBIGUOUS),
        unresolved_count=sum(1 for row in rows if row.latest_outcome_class == FgReceiveResolutionOutcome.UNRESOLVED),
        with_final_truth_count=sum(1 for row in rows if row.has_final_truth),
        without_final_truth_count=sum(1 for row in rows if not row.has_final_truth),
        with_evidence_snapshot_count=sum(1 for row in rows if row.has_evidence_snapshot),
        without_evidence_snapshot_count=sum(1 for row in rows if not row.has_evidence_snapshot),
    )


def get_fg_receive_step47_activation_state() -> dict[str, bool]:
    return {
        "admitted_source_activation_active": FG_RECEIVE_STEP47_ADMITTED_SOURCE_ACTIVE,
        "runtime_production_use_authorized": FG_RECEIVE_STEP47_RUNTIME_PRODUCTION_USE_AUTHORIZED,
    }


def _resolve_event_time_location(*, db: Session, fg_receive: WorkOrderFgReceive) -> _ResolutionResult:
    source_label_token = _normalize_optional_text(fg_receive.fg_handling_unit_label, upper=True)
    if source_label_token is None:
        return _ResolutionResult(
            outcome_class=FgReceiveResolutionOutcome.UNRESOLVED,
            source_label_token=None,
            resolved_location_code=None,
            failure_reason="FG receive handling-unit label is missing for event-time location resolution",
            label=None,
            mapping=None,
            location=None,
        )

    label = db.query(LocationLabel).filter(LocationLabel.label_token == source_label_token).first()
    if label is None:
        return _ResolutionResult(
            outcome_class=FgReceiveResolutionOutcome.FAILED,
            source_label_token=source_label_token,
            resolved_location_code=None,
            failure_reason=f"Location label token was not found: label_token={source_label_token}",
            label=None,
            mapping=None,
            location=None,
        )
    if _status(label.status) != "ACTIVE":
        return _ResolutionResult(
            outcome_class=FgReceiveResolutionOutcome.FAILED,
            source_label_token=source_label_token,
            resolved_location_code=None,
            failure_reason=f"Location label token is not active: label_token={source_label_token}, status={label.status}",
            label=label,
            mapping=None,
            location=None,
        )

    event_time = fg_receive.received_at
    candidate_mappings = [
        row
        for row in db.query(LabelLocationMapping).filter(LabelLocationMapping.location_label_id == label.id).all()
        if _status(row.status) == "ACTIVE" and row.effective_from <= event_time and (row.effective_to is None or event_time < row.effective_to)
    ]
    if len(candidate_mappings) > 1:
        return _ResolutionResult(
            outcome_class=FgReceiveResolutionOutcome.AMBIGUOUS,
            source_label_token=source_label_token,
            resolved_location_code=None,
            failure_reason=f"Multiple active event-time mappings were found: label_token={source_label_token}",
            label=label,
            mapping=None,
            location=None,
        )
    if not candidate_mappings:
        return _ResolutionResult(
            outcome_class=FgReceiveResolutionOutcome.FAILED,
            source_label_token=source_label_token,
            resolved_location_code=None,
            failure_reason=f"No active event-time mapping was found: label_token={source_label_token}",
            label=label,
            mapping=None,
            location=None,
        )

    mapping = candidate_mappings[0]
    location = db.query(PhysicalLocation).filter(PhysicalLocation.id == mapping.physical_location_id).first()
    if location is None:
        return _ResolutionResult(
            outcome_class=FgReceiveResolutionOutcome.FAILED,
            source_label_token=source_label_token,
            resolved_location_code=None,
            failure_reason=f"Mapped physical location was not found: mapping_id={mapping.id}",
            label=label,
            mapping=mapping,
            location=None,
        )
    if _status(location.status) != "ACTIVE":
        return _ResolutionResult(
            outcome_class=FgReceiveResolutionOutcome.FAILED,
            source_label_token=source_label_token,
            resolved_location_code=None,
            failure_reason=f"Mapped physical location is not active: location_code={location.location_code}, status={location.status}",
            label=label,
            mapping=mapping,
            location=location,
        )

    return _ResolutionResult(
        outcome_class=FgReceiveResolutionOutcome.SUCCESS,
        source_label_token=source_label_token,
        resolved_location_code=str(location.location_code or "").strip(),
        failure_reason=None,
        label=label,
        mapping=mapping,
        location=location,
    )


def _create_evidence_snapshot(
    *,
    db: Session,
    fg_receive: WorkOrderFgReceive,
    resolution: _ResolutionResult,
    now: datetime,
) -> FgReceiveLocationEvidenceSnapshot | None:
    if resolution.source_label_token is None and resolution.label is None and resolution.mapping is None and resolution.location is None:
        return None

    row = FgReceiveLocationEvidenceSnapshot(
        fg_receive_id=fg_receive.id,
        source_label_token=resolution.source_label_token,
        label_type=resolution.label.label_type if resolution.label is not None else None,
        location_label_id=resolution.label.id if resolution.label is not None else None,
        label_status=resolution.label.status if resolution.label is not None else None,
        label_matched=resolution.label is not None,
        matched_mapping_id=resolution.mapping.id if resolution.mapping is not None else None,
        mapping_status=resolution.mapping.status if resolution.mapping is not None else None,
        matched_location_id=resolution.location.id if resolution.location is not None else None,
        matched_location_code=resolution.location.location_code if resolution.location is not None else None,
        matched_location_status=resolution.location.status if resolution.location is not None else None,
        mapping_effective_from=resolution.mapping.effective_from if resolution.mapping is not None else None,
        mapping_effective_to=resolution.mapping.effective_to if resolution.mapping is not None else None,
        event_received_at=fg_receive.received_at,
        captured_at=now,
        failure_reason=resolution.failure_reason,
    )
    db.add(row)
    db.flush()
    return row


def _create_legal_position_row(
    *,
    db: Session,
    fg_receive: WorkOrderFgReceive,
    bound_location_code: str,
    posted_by: str,
    occurred_at: datetime,
    remark: str | None,
) -> StockLedger:
    work_order, item_master = _resolve_inventory_subject(db=db, fg_receive=fg_receive)
    base_qty, base_uom = _resolve_base_quantity_and_uom(
        item_master=item_master,
        txn_qty=float(fg_receive.txn_qty),
        txn_uom=str(fg_receive.txn_uom or "").strip().upper(),
    )
    row = StockLedger(
        org_id="demo-org",
        ledger_no="PENDING",
        item_id=str(item_master.material_code or "").strip(),
        item_code=str(item_master.material_code or "").strip(),
        location_id=bound_location_code,
        txn_type=LEGACY_TXN_TYPE,
        movement_type=MOVEMENT_TYPE,
        stock_bucket=STOCK_BUCKET,
        qty=base_qty,
        uom=base_uom,
        txn_qty=float(fg_receive.txn_qty),
        txn_uom=str(fg_receive.txn_uom or "").strip().upper(),
        base_qty=base_qty,
        base_uom=base_uom,
        ref_type="FG_RECEIVE_STEP47",
        ref_id=str(fg_receive.id),
        note=_normalize_optional_text(remark),
        source_event_type=SOURCE_EVENT_TYPE,
        source_event_id=fg_receive.id,
        work_order_id=work_order.id,
        sales_order_id=work_order.sales_order_id,
        work_order_no=work_order.work_order_no,
        posted_by=posted_by,
        remark=_normalize_optional_text(remark),
        posted_at=occurred_at,
        occurred_at=occurred_at,
    )
    db.add(row)
    db.flush()
    row.ledger_no = f"SLED-{int(row.id):06d}"
    db.add(row)
    db.flush()
    return row


def _resolve_inventory_subject(*, db: Session, fg_receive: WorkOrderFgReceive) -> tuple[WorkOrder, RawMaterial]:
    work_order = db.query(WorkOrder).filter(WorkOrder.id == fg_receive.work_order_id).first()
    if work_order is None:
        raise HTTPException(
            status_code=409,
            detail=f"FG receive work order could not be resolved for Step 47 legal-position write: fg_receive_id={fg_receive.id}",
        )

    product = db.query(Product).filter(Product.id == work_order.product_id).first()
    product_model_no = str(product.model_no or "").strip() if product is not None else ""
    if not product_model_no:
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive item resolution failed through work_order -> product.model_no -> RawMaterial.material_code: "
                f"fg_receive_id={fg_receive.id}, work_order_id={work_order.id}"
            ),
        )

    item_master = db.query(RawMaterial).filter(RawMaterial.material_code == product_model_no).first()
    if item_master is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive item resolution failed through work_order -> product.model_no -> RawMaterial.material_code: "
                f"fg_receive_id={fg_receive.id}, work_order_id={work_order.id}, product_model_no={product_model_no}"
            ),
        )
    return work_order, item_master


def _resolve_base_quantity_and_uom(*, item_master: RawMaterial, txn_qty: float, txn_uom: str) -> tuple[float, str]:
    base_uom = str(item_master.unit or "").strip().upper()
    if not base_uom:
        raise HTTPException(
            status_code=409,
            detail=f"FG receive Step 47 base_uom is missing for item_code={item_master.material_code}",
        )
    if txn_uom == base_uom:
        return txn_qty, base_uom

    conversion_type = str(item_master.conversion_type or "").strip().upper()
    if conversion_type != "STANDARD":
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive Step 47 conversion could not be resolved through SF-01: "
                f"item_code={item_master.material_code}, conversion_type={item_master.conversion_type}"
            ),
        )
    ratio = float(item_master.standard_conversion_ratio or 0)
    if ratio <= 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "FG receive Step 47 conversion could not be resolved through SF-01: "
                f"item_code={item_master.material_code}, standard_conversion_ratio={item_master.standard_conversion_ratio}"
            ),
        )
    return txn_qty * ratio, base_uom


def _guard_no_existing_final_truth(*, db: Session, fg_receive_id: int) -> None:
    existing = _get_final_truth(db=db, fg_receive_id=fg_receive_id)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"FG receive Step 47 final truth already exists and ordinary re-resolution is not allowed: fg_receive_id={fg_receive_id}",
        )


def _guard_no_existing_position_write(*, db: Session, fg_receive_id: int) -> None:
    existing = (
        db.query(StockLedger)
        .filter(StockLedger.source_event_type == SOURCE_EVENT_TYPE)
        .filter(StockLedger.source_event_id == fg_receive_id)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"FG receive Step 47 legal-position write is blocked because a stock ledger row already exists: fg_receive_id={fg_receive_id}",
        )


def _list_attempt_rows(*, db: Session, fg_receive_id: int) -> list[FgReceiveLocationResolutionAttempt]:
    return (
        db.query(FgReceiveLocationResolutionAttempt)
        .filter(FgReceiveLocationResolutionAttempt.fg_receive_id == fg_receive_id)
        .order_by(FgReceiveLocationResolutionAttempt.attempted_at.desc(), FgReceiveLocationResolutionAttempt.id.desc())
        .all()
    )


def _list_evidence_rows(*, db: Session, fg_receive_id: int) -> list[FgReceiveLocationEvidenceSnapshot]:
    return (
        db.query(FgReceiveLocationEvidenceSnapshot)
        .filter(FgReceiveLocationEvidenceSnapshot.fg_receive_id == fg_receive_id)
        .order_by(FgReceiveLocationEvidenceSnapshot.captured_at.desc(), FgReceiveLocationEvidenceSnapshot.id.desc())
        .all()
    )


def _get_final_truth(*, db: Session, fg_receive_id: int) -> FgReceiveEventTruth | None:
    return db.query(FgReceiveEventTruth).filter(FgReceiveEventTruth.fg_receive_id == fg_receive_id).first()


def _to_attempt_read(row: FgReceiveLocationResolutionAttempt) -> FgReceiveAttemptRead:
    return FgReceiveAttemptRead(
        attempt_id=int(row.id),
        source_label_token=row.source_label_token,
        outcome_class=FgReceiveResolutionOutcome(str(row.outcome_class)),
        resolved_location_code=row.resolved_location_code,
        failure_reason=row.failure_reason,
        evidence_snapshot_id=row.evidence_snapshot_id,
        attempted_at=row.attempted_at,
        completed_at=row.completed_at,
        attempted_by=str(row.attempted_by or ""),
    )


def _to_evidence_read(row: FgReceiveLocationEvidenceSnapshot) -> FgReceiveEvidenceSnapshotRead:
    return FgReceiveEvidenceSnapshotRead(
        evidence_snapshot_id=int(row.id),
        source_label_token=row.source_label_token,
        label_type=row.label_type,
        location_label_id=row.location_label_id,
        label_status=row.label_status,
        label_matched=bool(row.label_matched),
        matched_mapping_id=row.matched_mapping_id,
        mapping_status=row.mapping_status,
        matched_location_id=row.matched_location_id,
        matched_location_code=row.matched_location_code,
        matched_location_status=row.matched_location_status,
        mapping_effective_from=row.mapping_effective_from,
        mapping_effective_to=row.mapping_effective_to,
        event_received_at=row.event_received_at,
        captured_at=row.captured_at,
        evidence_source=str(row.evidence_source or ""),
        failure_reason=row.failure_reason,
    )


def _to_final_truth_read(row: FgReceiveEventTruth) -> FgReceiveFinalTruthRead:
    return FgReceiveFinalTruthRead(
        final_truth_id=int(row.id),
        bound_location_code=str(row.bound_location_code or ""),
        bound_from_resolution_attempt_id=int(row.bound_from_resolution_attempt_id),
        location_evidence_snapshot_ref=int(row.location_evidence_snapshot_ref),
        location_bound_at=row.location_bound_at,
    )


def _status(value: str | None) -> str:
    return str(value or "").strip().upper()


def _normalize_optional_text(value: str | None, *, upper: bool = False) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized.upper() if upper else normalized
