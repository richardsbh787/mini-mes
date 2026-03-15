from __future__ import annotations

from datetime import date
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database import Base
from models import Product, ProductionLine, RoutingHeader, RoutingStep, SalesOrder, WorkOrderRoutingSnapshot, WorkOrderRoutingSnapshotStep
from schemas import WorkOrderCreate
from app.bootstrap.work_order_routing_execution_state_schema import ensure_work_order_routing_execution_state_columns
from app.services.work_order_mainline import create_work_order_record
from app.services.work_order_routing_step_active import guard_work_order_routing_snapshot_active_step
from app.services.work_order_routing_step_active_release import guard_work_order_routing_snapshot_active_step_release


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    ensure_work_order_routing_execution_state_columns(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def _add_sales_order(db: Session, order_no: str) -> SalesOrder:
    row = SalesOrder(
        order_no=order_no,
        customer_name="Test Customer",
        order_date=date(2026, 3, 12),
        status="OPEN",
    )
    db.add(row)
    db.flush()
    return row


def _add_product(db: Session, model_no: str) -> Product:
    row = Product(model_no=model_no, model_description=f"Product {model_no}")
    db.add(row)
    db.flush()
    return row


def _add_line(db: Session, line_name: str) -> ProductionLine:
    row = ProductionLine(
        line_name=line_name,
        working_hours_per_day=8.0,
        efficiency_rate=1.0,
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def _add_routing(db: Session, item_code: str) -> RoutingHeader:
    row = RoutingHeader(
        item_code=item_code,
        routing_code=f"R-{item_code}",
        routing_name=f"Routing {item_code}",
        status="ACTIVE",
    )
    db.add(row)
    db.flush()
    return row


def _add_step(
    db: Session,
    routing_id: int,
    seq_no: int,
    step_code: str,
    step_name: str,
    department: str,
    is_required: bool,
) -> RoutingStep:
    row = RoutingStep(
        routing_id=routing_id,
        seq_no=seq_no,
        step_code=step_code,
        step_name=step_name,
        department=department,
        is_required=is_required,
    )
    db.add(row)
    db.flush()
    return row


class WorkOrderRoutingExecutionStateTruthTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def _create_work_order_with_snapshot(self, db: Session, suffix: str, *, include_optional_pack: bool = True) -> int:
        sales_order = _add_sales_order(db, f"SO-TRUTH-{suffix}")
        product = _add_product(db, f"FG-TRUTH-{suffix}")
        line = _add_line(db, f"LINE-TRUTH-{suffix}")
        routing = _add_routing(db, f"FG-TRUTH-{suffix}")
        _add_step(db, routing.id, 10, "CUT", "Cutting", "Production", True)
        _add_step(db, routing.id, 20, "ASSY", "Assembly", "Production", True)
        if include_optional_pack:
            _add_step(db, routing.id, 30, "PACK", "Packing", "Packing", False)
        db.commit()

        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no=f"WO-TRUTH-{suffix}",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                routing_id=routing.id,
                planned_hours=4.0,
                priority="NORMAL",
                promise_date=date(2026, 4, 9),
                is_material_ready=True,
            ),
        )
        return work_order.id

    def _snapshot_steps(self, db: Session, work_order_id: int) -> list[WorkOrderRoutingSnapshotStep]:
        snapshot = (
            db.query(WorkOrderRoutingSnapshot)
            .filter(WorkOrderRoutingSnapshot.work_order_id == work_order_id)
            .one()
        )
        return (
            db.query(WorkOrderRoutingSnapshotStep)
            .filter(WorkOrderRoutingSnapshotStep.snapshot_id == snapshot.id)
            .order_by(WorkOrderRoutingSnapshotStep.seq_no.asc(), WorkOrderRoutingSnapshotStep.id.asc())
            .all()
        )

    def test_new_snapshot_step_rows_default_to_pending(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "1")

        rows = self._snapshot_steps(db, work_order_id)
        self.assertEqual(
            [
                (row.execution_status, row.started_at, row.started_by, row.completed_at, row.completed_by)
                for row in rows
            ],
            [
                ("PENDING", None, None, None, None),
                ("PENDING", None, None, None, None),
                ("PENDING", None, None, None, None),
            ],
        )

    def test_successful_start_writes_active_on_exact_step_row(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "2")

        active = guard_work_order_routing_snapshot_active_step(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=10,
            target_seq_no=20,
            active_seq_no=20,
            started_by="operator-a",
        )

        rows = self._snapshot_steps(db, work_order_id)
        self.assertEqual(active.active_step.seq_no, 20)
        self.assertEqual([(row.seq_no, row.execution_status) for row in rows], [(10, "PENDING"), (20, "ACTIVE"), (30, "PENDING")])
        self.assertIsNotNone(rows[1].started_at)
        self.assertEqual(rows[1].started_by, "operator-a")

    def test_same_snapshot_cannot_end_up_with_two_active_rows(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "3")

        guard_work_order_routing_snapshot_active_step(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=10,
            target_seq_no=20,
            active_seq_no=20,
            started_by="operator-a",
        )

        with self.assertRaises(HTTPException) as exc:
            guard_work_order_routing_snapshot_active_step(
                db=db,
                work_order_id=work_order_id,
                current_seq_no=20,
                target_seq_no=30,
                active_seq_no=30,
                started_by="operator-b",
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(exc.exception.detail, "work order already has a different active step")
        self.assertEqual(
            [(row.seq_no, row.execution_status) for row in self._snapshot_steps(db, work_order_id)],
            [(10, "PENDING"), (20, "ACTIVE"), (30, "PENDING")],
        )

    def test_successful_active_release_writes_done_on_exact_step_row(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "4")

        guard_work_order_routing_snapshot_active_step(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=10,
            target_seq_no=20,
            active_seq_no=20,
            started_by="operator-a",
        )

        release = guard_work_order_routing_snapshot_active_step_release(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=20,
            target_seq_no=20,
            release_seq_no=20,
            completed_by="operator-b",
        )

        rows = self._snapshot_steps(db, work_order_id)
        self.assertTrue(release.release_allowed)
        self.assertEqual([(row.seq_no, row.execution_status) for row in rows], [(10, "PENDING"), (20, "DONE"), (30, "PENDING")])
        self.assertIsNotNone(rows[1].completed_at)
        self.assertEqual(rows[1].completed_by, "operator-b")

    def test_required_all_done_and_no_active_derives_routing_completed_true(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "5", include_optional_pack=False)

        guard_work_order_routing_snapshot_active_step(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=10,
            target_seq_no=10,
            active_seq_no=10,
            started_by="operator-a",
        )
        guard_work_order_routing_snapshot_active_step_release(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=10,
            target_seq_no=10,
            release_seq_no=10,
            completed_by="operator-a",
        )
        guard_work_order_routing_snapshot_active_step(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=20,
            target_seq_no=20,
            active_seq_no=20,
            started_by="operator-b",
        )
        guard_work_order_routing_snapshot_active_step_release(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=20,
            target_seq_no=20,
            release_seq_no=20,
            completed_by="operator-b",
        )

        rows = self._snapshot_steps(db, work_order_id)
        has_active = any(row.execution_status == "ACTIVE" for row in rows)
        is_routing_completed = all(
            row.execution_status == "DONE" for row in rows if row.is_required
        ) and not has_active
        self.assertTrue(is_routing_completed)

    def test_optional_step_not_done_does_not_block_routing_completed(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "6")

        guard_work_order_routing_snapshot_active_step(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=10,
            target_seq_no=10,
            active_seq_no=10,
            started_by="operator-a",
        )
        guard_work_order_routing_snapshot_active_step_release(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=10,
            target_seq_no=10,
            release_seq_no=10,
            completed_by="operator-a",
        )
        guard_work_order_routing_snapshot_active_step(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=20,
            target_seq_no=20,
            active_seq_no=20,
            started_by="operator-b",
        )
        guard_work_order_routing_snapshot_active_step_release(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=20,
            target_seq_no=20,
            release_seq_no=20,
            completed_by="operator-b",
        )

        rows = self._snapshot_steps(db, work_order_id)
        has_active = any(row.execution_status == "ACTIVE" for row in rows)
        is_routing_completed = all(
            row.execution_status == "DONE" for row in rows if row.is_required
        ) and not has_active
        self.assertTrue(is_routing_completed)
        self.assertEqual(rows[2].execution_status, "PENDING")

    def test_rollback_failure_does_not_leave_half_written_execution_state(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "7")

        original_commit = db.commit

        def fail_commit():
            raise RuntimeError("boom")

        db.commit = fail_commit
        try:
            with self.assertRaises(HTTPException) as exc:
                guard_work_order_routing_snapshot_active_step(
                    db=db,
                    work_order_id=work_order_id,
                    current_seq_no=10,
                    target_seq_no=20,
                    active_seq_no=20,
                    started_by="operator-a",
                )
        finally:
            db.commit = original_commit

        self.assertEqual(exc.exception.status_code, 500)
        self.assertEqual(exc.exception.detail, f"WorkOrder routing step start failed and rolled back: work_order_id={work_order_id}")
        self.assertEqual(
            [(row.seq_no, row.execution_status, row.started_by) for row in self._snapshot_steps(db, work_order_id)],
            [(10, "PENDING", None), (20, "PENDING", None), (30, "PENDING", None)],
        )


if __name__ == "__main__":
    unittest.main()
