from __future__ import annotations

from datetime import datetime
from math import floor
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.step41_anchor_control import (
    DamagedLabelRecordCreate,
    FailureQrSheetRecordCreate,
    FallbackSessionCreate,
    LabelInstanceCreate,
    LabelRangeBatchCreate,
    ManualExecutionCorrectionCreate,
    ManualExecutionEntryCreate,
    PackingDetailInput,
)
from models import (
    DamagedLabelRecord,
    ExpectedPrintPlan,
    FailureQrSheetRecord,
    FallbackSession,
    LabelInstance,
    LabelRangeBatch,
    ManualExecutionEntry,
    PackingDetail,
    ReplacementLabelLink,
    WorkOrder,
)


def calculate_expected_print_plan(
    db: Session,
    *,
    work_order_id: int,
    anchor_type: str,
    packing_input: PackingDetailInput,
) -> ExpectedPrintPlan:
    work_order = _load_work_order(db=db, work_order_id=work_order_id)
    basis_qty = _require_planned_qty(work_order)

    full_pack_count = int(floor(basis_qty / packing_input.pack_unit_qty))
    partial_pack_qty = round(basis_qty - (full_pack_count * packing_input.pack_unit_qty), 6)
    expected_label_qty = full_pack_count + (1 if packing_input.allow_partial and partial_pack_qty > 0 else 0)

    packing_detail = (
        db.query(PackingDetail)
        .filter(PackingDetail.work_order_id == work_order_id)
        .filter(PackingDetail.process_context == packing_input.process_context.value)
        .filter(PackingDetail.label_type == packing_input.label_type)
        .one_or_none()
    )
    if packing_detail is None:
        packing_detail = PackingDetail(
            work_order_id=work_order_id,
            process_context=packing_input.process_context.value,
            label_type=packing_input.label_type,
        )
        db.add(packing_detail)

    packing_detail.basis_qty = basis_qty
    packing_detail.pack_unit_qty = packing_input.pack_unit_qty
    packing_detail.full_pack_count = full_pack_count
    packing_detail.partial_pack_qty = partial_pack_qty
    packing_detail.expected_label_qty = expected_label_qty
    packing_detail.allow_partial = packing_input.allow_partial

    plan = (
        db.query(ExpectedPrintPlan)
        .filter(ExpectedPrintPlan.work_order_id == work_order_id)
        .filter(ExpectedPrintPlan.anchor_type == _normalize_code(anchor_type))
        .filter(ExpectedPrintPlan.label_type == packing_input.label_type)
        .filter(ExpectedPrintPlan.process_context == packing_input.process_context.value)
        .one_or_none()
    )
    if plan is None:
        plan = ExpectedPrintPlan(
            work_order_id=work_order_id,
            anchor_type=_normalize_code(anchor_type),
            label_type=packing_input.label_type,
            process_context=packing_input.process_context.value,
        )
        db.add(plan)

    printed_label_qty = plan.printed_label_qty or 0
    remaining_printable_qty = max(expected_label_qty - printed_label_qty, 0)

    plan.basis_qty = basis_qty
    plan.expected_label_qty = expected_label_qty
    plan.printed_label_qty = printed_label_qty
    plan.remaining_printable_qty = remaining_printable_qty
    plan.calculated_at = datetime.utcnow()

    packing_detail.printed_label_qty = printed_label_qty
    packing_detail.remaining_printable_qty = remaining_printable_qty

    db.flush()
    return plan


def create_label_range_batch(db: Session, payload: LabelRangeBatchCreate) -> LabelRangeBatch:
    range_qty = payload.range_last_no - payload.range_start_no + 1
    expected_plan_qty = _resolve_expected_plan_qty(
        db=db,
        work_order_id=payload.work_order_id,
        anchor_type=payload.anchor_type,
    )
    if payload.planned_qty != expected_plan_qty:
        raise HTTPException(status_code=409, detail="label range batch planned_qty must match the system-derived expected print quantity")
    if range_qty != expected_plan_qty:
        raise HTTPException(status_code=409, detail="label range batch range quantity must align exactly with the system-derived expected print quantity")

    overlapping_batch = (
        db.query(LabelRangeBatch)
        .filter(LabelRangeBatch.work_order_id == payload.work_order_id)
        .filter(LabelRangeBatch.anchor_type == payload.anchor_type)
        .filter(LabelRangeBatch.range_start_no <= payload.range_last_no)
        .filter(LabelRangeBatch.range_last_no >= payload.range_start_no)
        .one_or_none()
    )
    if overlapping_batch is not None:
        raise HTTPException(status_code=409, detail="label range overlaps an existing batch in the same scope")

    batch = LabelRangeBatch(
        range_batch_id=payload.range_batch_id,
        work_order_id=payload.work_order_id,
        anchor_type=payload.anchor_type,
        range_start_no=payload.range_start_no,
        range_last_no=payload.range_last_no,
        range_qty=range_qty,
        planned_qty=payload.planned_qty,
        issued_qty=range_qty,
        printed_qty=0,
        issued_to_line_qty=0,
        used_qty=0,
        damaged_qty=0,
        void_qty=0,
        unused_qty=range_qty,
        issued_by=payload.issued_by,
        issued_at=payload.issued_at,
        status="OPEN",
    )
    db.add(batch)
    db.flush()
    return batch


def register_label_print(
    db: Session,
    *,
    plan_id: int,
    payload: LabelInstanceCreate,
) -> LabelInstance:
    plan = db.query(ExpectedPrintPlan).filter(ExpectedPrintPlan.id == plan_id).one_or_none()
    if plan is None:
        raise HTTPException(status_code=404, detail="expected print plan not found")
    if (plan.remaining_printable_qty or 0) <= 0:
        raise HTTPException(status_code=409, detail="expected printable quantity has been exhausted")

    batch = _load_range_batch(db=db, range_batch_id=payload.range_batch_id)
    if batch.work_order_id != payload.work_order_id or batch.anchor_type != payload.anchor_type:
        raise HTTPException(status_code=409, detail="label print request must stay inside the issued batch scope")
    if (batch.printed_qty or 0) >= (batch.issued_qty or 0):
        raise HTTPException(status_code=409, detail="label range batch issued capacity has been exhausted")
    _assert_seq_inside_batch(batch=batch, run_seq_no=payload.run_seq_no)
    _guard_label_sequence_uniqueness(db=db, payload=payload)

    instance = LabelInstance(
        label_instance_uuid=str(uuid4()),
        anchor_type=payload.anchor_type,
        anchor_value=payload.anchor_value,
        work_order_id=payload.work_order_id,
        run_seq_no=payload.run_seq_no,
        range_batch_id=payload.range_batch_id,
        print_status="PRINTED",
        print_attempt_no=1,
        printed_by=payload.printed_by,
        printed_at=payload.printed_at,
        reprint_reason=payload.reprint_reason,
        replaced_from_label_id=payload.replaced_from_label_id,
    )
    db.add(instance)

    batch.printed_qty = (batch.printed_qty or 0) + 1
    plan.printed_label_qty = (plan.printed_label_qty or 0) + 1
    plan.remaining_printable_qty = max((plan.expected_label_qty or 0) - plan.printed_label_qty, 0)

    packing_detail = (
        db.query(PackingDetail)
        .filter(PackingDetail.work_order_id == plan.work_order_id)
        .filter(PackingDetail.process_context == plan.process_context)
        .filter(PackingDetail.label_type == plan.label_type)
        .one_or_none()
    )
    if packing_detail is not None:
        packing_detail.printed_label_qty = plan.printed_label_qty
        packing_detail.remaining_printable_qty = plan.remaining_printable_qty

    db.flush()
    return instance


def mark_label_used(db: Session, *, label_instance_id: int, used_at: datetime | None = None) -> LabelInstance:
    instance = _load_label_instance(db=db, label_instance_id=label_instance_id)
    batch = _load_range_batch(db=db, range_batch_id=instance.range_batch_id)
    _guard_label_status_transition(instance=instance, expected_status="PRINTED")

    instance.print_status = "USED"
    instance.issued_to_line_at = used_at or datetime.utcnow()
    batch.issued_to_line_qty = (batch.issued_to_line_qty or 0) + 1
    batch.used_qty = (batch.used_qty or 0) + 1
    _recalculate_unused_qty(batch)
    db.flush()
    return instance


def mark_label_void(db: Session, *, label_instance_id: int, void_reason: str) -> LabelInstance:
    instance = _load_label_instance(db=db, label_instance_id=label_instance_id)
    batch = _load_range_batch(db=db, range_batch_id=instance.range_batch_id)
    _guard_label_status_transition(instance=instance, expected_status="PRINTED")

    instance.print_status = "VOID"
    instance.void_reason = str(void_reason or "").strip()
    batch.void_qty = (batch.void_qty or 0) + 1
    _recalculate_unused_qty(batch)
    db.flush()
    return instance


def record_damaged_label(
    db: Session,
    *,
    label_instance_id: int,
    payload: DamagedLabelRecordCreate,
    evidence: FailureQrSheetRecordCreate,
    replacement_label_id: int | None = None,
) -> DamagedLabelRecord:
    instance = _load_label_instance(db=db, label_instance_id=label_instance_id)
    batch = _load_range_batch(db=db, range_batch_id=instance.range_batch_id)
    _guard_label_status_transition(instance=instance, expected_status="PRINTED")

    damaged_record = DamagedLabelRecord(**payload.model_dump())
    db.add(damaged_record)
    db.flush()

    evidence_row = FailureQrSheetRecord(
        damaged_label_id=damaged_record.id,
        failure_qr_sheet_no=evidence.failure_qr_sheet_no,
        attached_by=evidence.attached_by,
        attached_at=evidence.attached_at,
    )
    db.add(evidence_row)

    _invalidate_damaged_label(instance)
    batch.damaged_qty = (batch.damaged_qty or 0) + 1
    _recalculate_unused_qty(batch)

    if replacement_label_id is not None:
        _load_label_instance(db=db, label_instance_id=replacement_label_id)
        db.add(
            ReplacementLabelLink(
                damaged_label_id=damaged_record.id,
                replacement_label_id=replacement_label_id,
            )
        )

    db.flush()
    return damaged_record


def create_fallback_session(db: Session, payload: FallbackSessionCreate) -> FallbackSession:
    session = FallbackSession(**payload.model_dump())
    db.add(session)
    db.flush()
    return session


def create_manual_execution_entry(
    db: Session,
    *,
    payload: ManualExecutionEntryCreate,
    fallback_session_id: int,
) -> ManualExecutionEntry:
    fallback_session = db.query(FallbackSession).filter(FallbackSession.id == fallback_session_id).one_or_none()
    if fallback_session is None:
        raise HTTPException(status_code=404, detail="fallback session not found")
    if fallback_session.status != "OPEN":
        raise HTTPException(status_code=409, detail="manual fallback requires an OPEN fallback session")
    if not (fallback_session.effective_from <= payload.override_at <= fallback_session.effective_to):
        raise HTTPException(status_code=409, detail="manual fallback must stay within the approved fallback session window")

    row = ManualExecutionEntry(**payload.model_dump(), original_manual_entry_id=None)
    db.add(row)
    db.flush()
    return row


def create_manual_execution_correction(
    db: Session,
    *,
    payload: ManualExecutionCorrectionCreate,
) -> ManualExecutionEntry:
    original = db.query(ManualExecutionEntry).filter(ManualExecutionEntry.id == payload.original_manual_entry_id).one_or_none()
    if original is None:
        raise HTTPException(status_code=404, detail="original manual execution entry not found")

    correction = ManualExecutionEntry(**payload.model_dump())
    db.add(correction)
    db.flush()
    return correction


def close_label_range_batch(db: Session, *, range_batch_id: str) -> LabelRangeBatch:
    batch = _load_range_batch(db=db, range_batch_id=range_batch_id)
    _assert_final_conservation(batch)
    batch.status = "CLOSED"
    db.flush()
    return batch


def validate_damaged_label_evidence_chain(
    db: Session,
    *,
    damaged_label_id: int,
) -> None:
    damaged = db.query(DamagedLabelRecord).filter(DamagedLabelRecord.id == damaged_label_id).one_or_none()
    if damaged is None:
        raise HTTPException(status_code=404, detail="damaged label record not found")

    evidence = (
        db.query(FailureQrSheetRecord)
        .filter(FailureQrSheetRecord.damaged_label_id == damaged_label_id)
        .one_or_none()
    )
    if evidence is None:
        raise HTTPException(status_code=409, detail="damaged label record must have failure QR evidence")

    if damaged.replacement_required:
        replacement = (
            db.query(ReplacementLabelLink)
            .filter(ReplacementLabelLink.damaged_label_id == damaged_label_id)
            .one_or_none()
        )
        if replacement is None:
            raise HTTPException(status_code=409, detail="damaged label replacement must keep an old-to-new link")


def _load_work_order(db: Session, *, work_order_id: int) -> WorkOrder:
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).one_or_none()
    if work_order is None:
        raise HTTPException(status_code=404, detail="work order not found")
    return work_order


def _resolve_expected_plan_qty(
    db: Session,
    *,
    work_order_id: int,
    anchor_type: str,
) -> int:
    plans = (
        db.query(ExpectedPrintPlan)
        .filter(ExpectedPrintPlan.work_order_id == work_order_id)
        .filter(ExpectedPrintPlan.anchor_type == _normalize_code(anchor_type))
        .all()
    )
    if not plans:
        raise HTTPException(status_code=409, detail="label range batch cannot be issued before the system-derived expected print plan exists")
    return int(sum(plan.expected_label_qty or 0 for plan in plans))


def _require_planned_qty(work_order: WorkOrder) -> float:
    if work_order.planned_qty is None:
        raise HTTPException(status_code=409, detail="work order planned_qty is required for Step 41A")
    return float(work_order.planned_qty)


def _load_range_batch(db: Session, *, range_batch_id: str) -> LabelRangeBatch:
    batch = db.query(LabelRangeBatch).filter(LabelRangeBatch.range_batch_id == _normalize_code(range_batch_id)).one_or_none()
    if batch is None:
        raise HTTPException(status_code=404, detail="label range batch not found")
    return batch


def _load_label_instance(db: Session, *, label_instance_id: int) -> LabelInstance:
    row = db.query(LabelInstance).filter(LabelInstance.id == label_instance_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="label instance not found")
    return row


def _assert_seq_inside_batch(*, batch: LabelRangeBatch, run_seq_no: int) -> None:
    if not (batch.range_start_no <= run_seq_no <= batch.range_last_no):
        raise HTTPException(status_code=409, detail="run sequence number is outside the issued label range")


def _guard_label_sequence_uniqueness(db: Session, *, payload: LabelInstanceCreate) -> None:
    existing = (
        db.query(LabelInstance)
        .filter(LabelInstance.work_order_id == payload.work_order_id)
        .filter(LabelInstance.anchor_type == payload.anchor_type)
        .filter(LabelInstance.run_seq_no == payload.run_seq_no)
        .one_or_none()
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="label run sequence number has already been issued and cannot be reused")


def _guard_label_status_transition(*, instance: LabelInstance, expected_status: str) -> None:
    if instance.print_status != expected_status:
        raise HTTPException(status_code=409, detail=f"label status transition requires {expected_status}, got {instance.print_status}")


def _invalidate_damaged_label(instance: LabelInstance) -> None:
    instance.print_status = "DAMAGED"
    instance.void_reason = "DAMAGED_INVALIDATED"


def _recalculate_unused_qty(batch: LabelRangeBatch) -> None:
    batch.unused_qty = batch.issued_qty - batch.used_qty - batch.damaged_qty - batch.void_qty
    if batch.unused_qty < 0:
        raise HTTPException(status_code=409, detail="label range batch counters became inconsistent")
    _assert_intermediate_consistency(batch)


def _assert_intermediate_consistency(batch: LabelRangeBatch) -> None:
    if batch.used_qty < 0 or batch.damaged_qty < 0 or batch.void_qty < 0 or batch.unused_qty < 0:
        raise HTTPException(status_code=409, detail="label range batch counters cannot be negative")
    if batch.used_qty + batch.damaged_qty + batch.void_qty + batch.unused_qty != batch.issued_qty:
        raise HTTPException(status_code=409, detail="label range batch counters failed conservation check")


def _assert_final_conservation(batch: LabelRangeBatch) -> None:
    total = batch.used_qty + batch.damaged_qty + batch.void_qty + batch.unused_qty
    if total != batch.issued_qty:
        raise HTTPException(status_code=409, detail="label range batch cannot close because conservation does not hold")


def _normalize_code(value: str) -> str:
    return str(value or "").strip().upper()
