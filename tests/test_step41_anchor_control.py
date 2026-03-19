from __future__ import annotations

import unittest
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.bootstrap.step41_anchor_control_schema import ensure_step41_anchor_control_schema
from app.schemas.step41_anchor_control import (
    DamagedLabelRecordCreate,
    FailureQrSheetRecordCreate,
    FallbackSessionCreate,
    LabelInstanceCreate,
    LabelRangeBatchCreate,
    ManualExecutionCorrectionCreate,
    ManualExecutionEntryCreate,
    PackingDetailInput,
    ProcessContext,
)
from app.services.step41_anchor_control import (
    calculate_expected_print_plan,
    close_label_range_batch,
    create_fallback_session,
    create_label_range_batch,
    create_manual_execution_correction,
    create_manual_execution_entry,
    mark_label_void,
    record_damaged_label,
    register_label_print,
    validate_damaged_label_evidence_chain,
)
from database import Base
from models import (
    ExpectedPrintPlan,
    FailureQrSheetRecord,
    FallbackSession,
    LabelRangeBatch,
    ManualExecutionEntry,
    Product,
    ProductionLine,
    ReplacementLabelLink,
    SalesOrder,
    WorkOrder,
)


def _make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    ensure_step41_anchor_control_schema(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


class Step41AnchorControlTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def _seed_work_order(self, db: Session, *, suffix: str, planned_qty: float | None = 23.0) -> WorkOrder:
        sales_order = SalesOrder(
            order_no=f"SO-41A-{suffix}",
            customer_name="Customer",
            order_date=date(2026, 3, 19),
            status="OPEN",
        )
        product = Product(model_no=f"FG-41A-{suffix}", model_description="Test FG")
        line = ProductionLine(
            line_name=f"LINE-41A-{suffix}",
            working_hours_per_day=8.0,
            efficiency_rate=1.0,
            is_active=True,
        )
        db.add_all([sales_order, product, line])
        db.flush()

        work_order = WorkOrder(
            work_order_no=f"WO-41A-{suffix}",
            sales_order_id=sales_order.id,
            product_id=product.id,
            production_line_id=line.id,
            planned_qty=planned_qty,
            planned_hours=4.0,
            actual_hours=0.0,
            remaining_hours=4.0,
            priority="NORMAL",
            promise_date=date(2026, 4, 19),
            is_material_ready=True,
            status="OPEN",
        )
        db.add(work_order)
        db.commit()
        db.refresh(work_order)
        return work_order

    def _create_plan_and_batch(self, db: Session, *, suffix: str = "A") -> tuple[ExpectedPrintPlan, LabelRangeBatch]:
        work_order = self._seed_work_order(db, suffix=suffix)
        plan = calculate_expected_print_plan(
            db,
            work_order_id=work_order.id,
            anchor_type="MAIN",
            packing_input=PackingDetailInput(
                process_context=ProcessContext.PACKING,
                label_type="carton",
                pack_unit_qty=10,
                allow_partial=True,
            ),
        )
        batch = create_label_range_batch(
            db,
            LabelRangeBatchCreate(
                range_batch_id=f"RB-{suffix}",
                work_order_id=work_order.id,
                anchor_type="MAIN",
                range_start_no=100,
                range_last_no=102,
                planned_qty=plan.expected_label_qty,
                issued_by="planner-a",
                issued_at=datetime(2026, 3, 19, 9, 0, 0),
            ),
        )
        db.commit()
        return plan, batch

    def test_basis_qty_must_come_from_work_order_planned_qty_only(self) -> None:
        db = self._new_db()
        work_order = self._seed_work_order(db, suffix="BASIS", planned_qty=23.0)

        plan = calculate_expected_print_plan(
            db,
            work_order_id=work_order.id,
            anchor_type="main",
            packing_input=PackingDetailInput(
                process_context=ProcessContext.PACKING,
                label_type="carton",
                pack_unit_qty=10,
                allow_partial=True,
            ),
        )

        self.assertEqual(plan.basis_qty, 23.0)
        self.assertEqual(plan.expected_label_qty, 3)

    def test_expected_print_qty_is_system_derived_not_operator_entered(self) -> None:
        db = self._new_db()
        work_order = self._seed_work_order(db, suffix="PLAN", planned_qty=21.0)

        plan = calculate_expected_print_plan(
            db,
            work_order_id=work_order.id,
            anchor_type="MAIN",
            packing_input=PackingDetailInput(
                process_context=ProcessContext.PACKING,
                label_type="carton",
                pack_unit_qty=10,
                allow_partial=False,
            ),
        )

        self.assertEqual(plan.expected_label_qty, 2)
        self.assertEqual(plan.remaining_printable_qty, 2)

    def test_expected_print_plan_requires_work_order_planned_qty(self) -> None:
        db = self._new_db()
        work_order = self._seed_work_order(db, suffix="NOPLAN", planned_qty=None)

        with self.assertRaises(HTTPException) as ctx:
            calculate_expected_print_plan(
                db,
                work_order_id=work_order.id,
                anchor_type="MAIN",
                packing_input=PackingDetailInput(
                    process_context=ProcessContext.PACKING,
                    label_type="carton",
                    pack_unit_qty=10,
                ),
            )

        self.assertEqual(ctx.exception.status_code, 409)

    def test_range_qty_formula_is_last_minus_start_plus_one(self) -> None:
        db = self._new_db()
        work_order = self._seed_work_order(db, suffix="RANGE", planned_qty=10.0)
        calculate_expected_print_plan(
            db,
            work_order_id=work_order.id,
            anchor_type="MAIN",
            packing_input=PackingDetailInput(
                process_context=ProcessContext.PACKING,
                label_type="carton",
                pack_unit_qty=1,
                allow_partial=False,
            ),
        )

        batch = create_label_range_batch(
            db,
            LabelRangeBatchCreate(
                range_batch_id="RB-RANGE",
                work_order_id=work_order.id,
                anchor_type="MAIN",
                range_start_no=15,
                range_last_no=24,
                planned_qty=10,
                issued_by="planner-a",
                issued_at=datetime(2026, 3, 19, 10, 0, 0),
            ),
        )

        self.assertEqual(batch.range_qty, 10)
        self.assertEqual(batch.issued_qty, 10)
        self.assertEqual(batch.unused_qty, 10)

    def test_non_overlapping_range_enforcement_blocks_same_scope_overlap(self) -> None:
        db = self._new_db()
        work_order = self._seed_work_order(db, suffix="OVERLAP", planned_qty=10.0)
        calculate_expected_print_plan(
            db,
            work_order_id=work_order.id,
            anchor_type="MAIN",
            packing_input=PackingDetailInput(
                process_context=ProcessContext.PACKING,
                label_type="carton",
                pack_unit_qty=1,
                allow_partial=False,
            ),
        )

        create_label_range_batch(
            db,
            LabelRangeBatchCreate(
                range_batch_id="RB-OVER-1",
                work_order_id=work_order.id,
                anchor_type="MAIN",
                range_start_no=1,
                range_last_no=10,
                planned_qty=10,
                issued_by="planner-a",
                issued_at=datetime(2026, 3, 19, 10, 0, 0),
            ),
        )

        with self.assertRaises(HTTPException) as ctx:
            create_label_range_batch(
                db,
                LabelRangeBatchCreate(
                    range_batch_id="RB-OVER-2",
                    work_order_id=work_order.id,
                    anchor_type="MAIN",
                    range_start_no=5,
                    range_last_no=14,
                    planned_qty=10,
                    issued_by="planner-b",
                    issued_at=datetime(2026, 3, 19, 10, 5, 0),
                ),
            )

        self.assertEqual(ctx.exception.status_code, 409)

    def test_range_batch_must_align_with_system_derived_expected_print_qty(self) -> None:
        db = self._new_db()
        work_order = self._seed_work_order(db, suffix="ALIGN", planned_qty=3.0)
        calculate_expected_print_plan(
            db,
            work_order_id=work_order.id,
            anchor_type="MAIN",
            packing_input=PackingDetailInput(
                process_context=ProcessContext.PACKING,
                label_type="carton",
                pack_unit_qty=1,
                allow_partial=False,
            ),
        )

        with self.assertRaises(HTTPException) as ctx:
            create_label_range_batch(
                db,
                LabelRangeBatchCreate(
                    range_batch_id="RB-ALIGN",
                    work_order_id=work_order.id,
                    anchor_type="MAIN",
                    range_start_no=1,
                    range_last_no=4,
                    planned_qty=4,
                    issued_by="planner-a",
                    issued_at=datetime(2026, 3, 19, 10, 0, 0),
                ),
            )

        self.assertEqual(ctx.exception.status_code, 409)

    def test_run_seq_no_is_unique_within_work_order_and_anchor_type(self) -> None:
        db = self._new_db()
        plan, batch = self._create_plan_and_batch(db, suffix="SEQ")

        register_label_print(
            db,
            plan_id=plan.id,
            payload=LabelInstanceCreate(
                anchor_type="MAIN",
                anchor_value="WO-SEQ-100",
                work_order_id=batch.work_order_id,
                run_seq_no=100,
                range_batch_id=batch.range_batch_id,
                printed_by="operator-a",
                printed_at=datetime(2026, 3, 19, 10, 0, 0),
            ),
        )
        db.commit()

        with self.assertRaises(HTTPException) as ctx:
            register_label_print(
                db,
                plan_id=plan.id,
                payload=LabelInstanceCreate(
                    anchor_type="MAIN",
                    anchor_value="WO-SEQ-100-DUP",
                    work_order_id=batch.work_order_id,
                    run_seq_no=100,
                    range_batch_id=batch.range_batch_id,
                    printed_by="operator-b",
                    printed_at=datetime(2026, 3, 19, 10, 1, 0),
                ),
            )

        self.assertEqual(ctx.exception.status_code, 409)

    def test_sequence_cannot_be_reused_after_void(self) -> None:
        db = self._new_db()
        plan, batch = self._create_plan_and_batch(db, suffix="VOID")

        label = register_label_print(
            db,
            plan_id=plan.id,
            payload=LabelInstanceCreate(
                anchor_type="MAIN",
                anchor_value="WO-VOID-100",
                work_order_id=batch.work_order_id,
                run_seq_no=100,
                range_batch_id=batch.range_batch_id,
                printed_by="operator-a",
                printed_at=datetime(2026, 3, 19, 10, 0, 0),
            ),
        )
        mark_label_void(db, label_instance_id=label.id, void_reason="Misprint")
        db.commit()

        batch = db.query(LabelRangeBatch).filter(LabelRangeBatch.id == batch.id).one()
        self.assertEqual(batch.void_qty, 1)
        self.assertEqual(batch.unused_qty, batch.issued_qty - 1)

        with self.assertRaises(HTTPException):
            register_label_print(
                db,
                plan_id=plan.id,
                payload=LabelInstanceCreate(
                    anchor_type="MAIN",
                    anchor_value="WO-VOID-100-RETRY",
                    work_order_id=batch.work_order_id,
                    run_seq_no=100,
                    range_batch_id=batch.range_batch_id,
                    printed_by="operator-b",
                    printed_at=datetime(2026, 3, 19, 10, 5, 0),
                ),
            )

    def test_immediate_batch_counter_updates_apply_after_damage_and_replacement(self) -> None:
        db = self._new_db()
        plan, batch = self._create_plan_and_batch(db, suffix="DMG")

        damaged_label = register_label_print(
            db,
            plan_id=plan.id,
            payload=LabelInstanceCreate(
                anchor_type="MAIN",
                anchor_value="WO-DMG-100",
                work_order_id=batch.work_order_id,
                run_seq_no=100,
                range_batch_id=batch.range_batch_id,
                printed_by="operator-a",
                printed_at=datetime(2026, 3, 19, 10, 0, 0),
            ),
        )
        replacement_label = register_label_print(
            db,
            plan_id=plan.id,
            payload=LabelInstanceCreate(
                anchor_type="MAIN",
                anchor_value="WO-DMG-101",
                work_order_id=batch.work_order_id,
                run_seq_no=101,
                range_batch_id=batch.range_batch_id,
                printed_by="operator-a",
                printed_at=datetime(2026, 3, 19, 10, 1, 0),
                replaced_from_label_id=damaged_label.id,
                reprint_reason="DAMAGED_REPLACEMENT",
            ),
        )

        damaged = record_damaged_label(
            db,
            label_instance_id=damaged_label.id,
            payload=DamagedLabelRecordCreate(
                anchor_type="MAIN",
                anchor_value=damaged_label.anchor_value,
                related_work_order=batch.work_order_id,
                label_serial=damaged_label.label_instance_uuid,
                damage_stage="PRINT",
                reported_by="qa-a",
                reported_at=datetime(2026, 3, 19, 10, 2, 0),
                reason="Print head smear",
                replacement_required=True,
            ),
            evidence=FailureQrSheetRecordCreate(
                failure_qr_sheet_no="FQR-001",
                attached_by="qa-a",
                attached_at=datetime(2026, 3, 19, 10, 3, 0),
            ),
            replacement_label_id=replacement_label.id,
        )
        db.commit()

        batch = db.query(LabelRangeBatch).filter(LabelRangeBatch.id == batch.id).one()
        self.assertEqual(batch.printed_qty, 2)
        self.assertEqual(batch.damaged_qty, 1)
        self.assertEqual(batch.unused_qty, batch.issued_qty - 1)

        replacement_link = db.query(ReplacementLabelLink).filter(ReplacementLabelLink.damaged_label_id == damaged.id).one()
        self.assertEqual(replacement_link.replacement_label_id, replacement_label.id)

        db.refresh(damaged_label)
        self.assertEqual(damaged_label.print_status, "DAMAGED")
        self.assertEqual(damaged_label.void_reason, "DAMAGED_INVALIDATED")

        with self.assertRaises(HTTPException):
            register_label_print(
                db,
                plan_id=plan.id,
                payload=LabelInstanceCreate(
                    anchor_type="MAIN",
                    anchor_value="WO-DMG-100-REUSE",
                    work_order_id=batch.work_order_id,
                    run_seq_no=100,
                    range_batch_id=batch.range_batch_id,
                    printed_by="operator-b",
                    printed_at=datetime(2026, 3, 19, 10, 4, 0),
                ),
            )

    def test_register_label_print_stops_at_batch_issued_capacity(self) -> None:
        db = self._new_db()
        plan, batch = self._create_plan_and_batch(db, suffix="CAP")

        register_label_print(
            db,
            plan_id=plan.id,
            payload=LabelInstanceCreate(
                anchor_type="MAIN",
                anchor_value="WO-CAP-100",
                work_order_id=batch.work_order_id,
                run_seq_no=100,
                range_batch_id=batch.range_batch_id,
                printed_by="operator-a",
                printed_at=datetime(2026, 3, 19, 10, 0, 0),
            ),
        )
        register_label_print(
            db,
            plan_id=plan.id,
            payload=LabelInstanceCreate(
                anchor_type="MAIN",
                anchor_value="WO-CAP-101",
                work_order_id=batch.work_order_id,
                run_seq_no=101,
                range_batch_id=batch.range_batch_id,
                printed_by="operator-a",
                printed_at=datetime(2026, 3, 19, 10, 1, 0),
            ),
        )
        register_label_print(
            db,
            plan_id=plan.id,
            payload=LabelInstanceCreate(
                anchor_type="MAIN",
                anchor_value="WO-CAP-102",
                work_order_id=batch.work_order_id,
                run_seq_no=102,
                range_batch_id=batch.range_batch_id,
                printed_by="operator-a",
                printed_at=datetime(2026, 3, 19, 10, 2, 0),
            ),
        )
        db.commit()

        with self.assertRaises(HTTPException) as ctx:
            register_label_print(
                db,
                plan_id=plan.id,
                payload=LabelInstanceCreate(
                    anchor_type="MAIN",
                    anchor_value="WO-CAP-103",
                    work_order_id=batch.work_order_id,
                    run_seq_no=103,
                    range_batch_id=batch.range_batch_id,
                    printed_by="operator-b",
                    printed_at=datetime(2026, 3, 19, 10, 3, 0),
                ),
            )

        self.assertEqual(ctx.exception.status_code, 409)

    def test_closed_batch_is_rejected_when_final_conservation_fails(self) -> None:
        db = self._new_db()
        _, batch = self._create_plan_and_batch(db, suffix="CLOSE")
        batch.used_qty = 2
        batch.damaged_qty = 1
        batch.void_qty = 0
        batch.unused_qty = 1
        db.flush()

        with self.assertRaises(HTTPException) as ctx:
            close_label_range_batch(db, range_batch_id=batch.range_batch_id)

        self.assertEqual(ctx.exception.status_code, 409)

    def test_correction_creates_new_linked_record_without_mutating_original(self) -> None:
        db = self._new_db()
        fallback = create_fallback_session(
            db,
            FallbackSessionCreate(
                line_or_station="PACK-01",
                effective_from=datetime(2026, 3, 19, 8, 0, 0),
                effective_to=datetime(2026, 3, 19, 12, 0, 0),
                reason_code="PRINTER_FAILURE",
                ordered_by="leader-a",
                approved_by="manager-a",
                witness="qa-a",
            ),
        )
        original = create_manual_execution_entry(
            db,
            fallback_session_id=fallback.id,
            payload=ManualExecutionEntryCreate(
                anchor_type="MAIN",
                anchor_value="WO-MAN-001",
                process_context=ProcessContext.PACKING,
                qty=3,
                reason_code="PRINTER_FAILURE",
                entered_by="operator-a",
                approved_by="manager-a",
                witness="qa-a",
                override_at=datetime(2026, 3, 19, 9, 0, 0),
                remark="fallback print note",
                status="MANUAL_FALLBACK",
            ),
        )
        db.commit()

        fallback = db.query(FallbackSession).filter(FallbackSession.id == fallback.id).one()
        self.assertEqual(fallback.status, "OPEN")

        correction = create_manual_execution_correction(
            db,
            payload=ManualExecutionCorrectionCreate(
                anchor_type="MAIN",
                anchor_value="WO-MAN-001-CORR",
                process_context=ProcessContext.PACKING,
                qty=2,
                reason_code="PRINTER_FAILURE",
                entered_by="operator-b",
                approved_by="manager-b",
                witness="qa-b",
                override_at=datetime(2026, 3, 19, 9, 30, 0),
                remark="corrected qty",
                original_manual_entry_id=original.id,
            ),
        )
        db.commit()

        original = db.query(ManualExecutionEntry).filter(ManualExecutionEntry.id == original.id).one()
        self.assertEqual(original.status, "MANUAL_FALLBACK")
        self.assertIsNone(original.original_manual_entry_id)
        self.assertEqual(correction.status, "CORRECTION")
        self.assertEqual(correction.original_manual_entry_id, original.id)

    def test_damaged_label_requires_record_replacement_link_and_failure_qr_evidence_chain(self) -> None:
        db = self._new_db()
        plan, batch = self._create_plan_and_batch(db, suffix="CHAIN")

        damaged_label = register_label_print(
            db,
            plan_id=plan.id,
            payload=LabelInstanceCreate(
                anchor_type="MAIN",
                anchor_value="WO-CHAIN-100",
                work_order_id=batch.work_order_id,
                run_seq_no=100,
                range_batch_id=batch.range_batch_id,
                printed_by="operator-a",
                printed_at=datetime(2026, 3, 19, 10, 0, 0),
            ),
        )
        replacement_label = register_label_print(
            db,
            plan_id=plan.id,
            payload=LabelInstanceCreate(
                anchor_type="MAIN",
                anchor_value="WO-CHAIN-101",
                work_order_id=batch.work_order_id,
                run_seq_no=101,
                range_batch_id=batch.range_batch_id,
                printed_by="operator-a",
                printed_at=datetime(2026, 3, 19, 10, 1, 0),
                replaced_from_label_id=damaged_label.id,
                reprint_reason="DAMAGED_REPLACEMENT",
            ),
        )
        damaged = record_damaged_label(
            db,
            label_instance_id=damaged_label.id,
            payload=DamagedLabelRecordCreate(
                anchor_type="MAIN",
                anchor_value=damaged_label.anchor_value,
                related_work_order=batch.work_order_id,
                label_serial=damaged_label.label_instance_uuid,
                damage_stage="LINE_USE",
                reported_by="qa-a",
                reported_at=datetime(2026, 3, 19, 10, 2, 0),
                reason="Unreadable label",
                replacement_required=True,
            ),
            evidence=FailureQrSheetRecordCreate(
                failure_qr_sheet_no="FQR-CHAIN-001",
                attached_by="qa-a",
                attached_at=datetime(2026, 3, 19, 10, 3, 0),
            ),
            replacement_label_id=replacement_label.id,
        )
        db.commit()

        validate_damaged_label_evidence_chain(db, damaged_label_id=damaged.id)

        evidence = db.query(FailureQrSheetRecord).filter(FailureQrSheetRecord.damaged_label_id == damaged.id).one()
        link = db.query(ReplacementLabelLink).filter(ReplacementLabelLink.damaged_label_id == damaged.id).one()
        self.assertEqual(evidence.failure_qr_sheet_no, "FQR-CHAIN-001")
        self.assertEqual(link.replacement_label_id, replacement_label.id)


if __name__ == "__main__":
    unittest.main()
