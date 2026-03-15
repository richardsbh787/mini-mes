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
from app.services.work_order_routing_execution_read import build_work_order_routing_execution_read
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


class WorkOrderRoutingExecutionReadTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def _create_work_order_with_snapshot(self, db: Session, suffix: str, *, include_optional_pack: bool = True) -> int:
        sales_order = _add_sales_order(db, f"SO-READX-{suffix}")
        product = _add_product(db, f"FG-READX-{suffix}")
        line = _add_line(db, f"LINE-READX-{suffix}")
        routing = _add_routing(db, f"FG-READX-{suffix}")
        _add_step(db, routing.id, 10, "CUT", "Cutting", "Production", True)
        _add_step(db, routing.id, 20, "ASSY", "Assembly", "Production", True)
        if include_optional_pack:
            _add_step(db, routing.id, 30, "PACK", "Packing", "Packing", False)
        db.commit()

        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no=f"WO-READX-{suffix}",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                routing_id=routing.id,
                planned_hours=4.0,
                priority="NORMAL",
                promise_date=date(2026, 4, 10),
                is_material_ready=True,
            ),
        )
        return work_order.id

    def _snapshot(self, db: Session, work_order_id: int) -> WorkOrderRoutingSnapshot:
        return (
            db.query(WorkOrderRoutingSnapshot)
            .filter(WorkOrderRoutingSnapshot.work_order_id == work_order_id)
            .one()
        )

    def _snapshot_steps(self, db: Session, work_order_id: int) -> list[WorkOrderRoutingSnapshotStep]:
        snapshot = self._snapshot(db, work_order_id)
        return (
            db.query(WorkOrderRoutingSnapshotStep)
            .filter(WorkOrderRoutingSnapshotStep.snapshot_id == snapshot.id)
            .order_by(WorkOrderRoutingSnapshotStep.seq_no.asc(), WorkOrderRoutingSnapshotStep.id.asc())
            .all()
        )

    def test_all_pending_snapshot_reads_no_active_and_not_completed(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "1")
        before = [(row.id, row.execution_status, row.started_at, row.completed_at) for row in self._snapshot_steps(db, work_order_id)]

        read = build_work_order_routing_execution_read(db=db, work_order_id=work_order_id)

        self.assertFalse(read.has_active_step)
        self.assertFalse(read.is_routing_completed)
        self.assertIsNone(read.active_step)
        self.assertEqual([step.step_status for step in read.steps], ["PENDING", "PENDING", "PENDING"])
        after = [(row.id, row.execution_status, row.started_at, row.completed_at) for row in self._snapshot_steps(db, work_order_id)]
        self.assertEqual(after, before)

    def test_one_active_row_returns_active_step_and_has_active_step_true(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "2")
        guard_work_order_routing_snapshot_active_step(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=10,
            target_seq_no=20,
            active_seq_no=20,
            started_by="operator-a",
        )

        read = build_work_order_routing_execution_read(db=db, work_order_id=work_order_id)

        self.assertTrue(read.has_active_step)
        self.assertEqual(read.active_step.seq_no, 20)
        self.assertEqual(read.active_step.step_status, "ACTIVE")

    def test_done_active_pending_mapping_reads_directly_from_persisted_step_rows(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "3")
        steps = self._snapshot_steps(db, work_order_id)
        steps[0].execution_status = "DONE"
        steps[1].execution_status = "ACTIVE"
        steps[2].execution_status = "PENDING"
        db.commit()

        read = build_work_order_routing_execution_read(db=db, work_order_id=work_order_id)

        self.assertEqual(
            [(step.seq_no, step.step_status) for step in read.steps],
            [(10, "DONE"), (20, "ACTIVE"), (30, "PENDING")],
        )

    def test_all_required_done_and_no_active_sets_routing_completed_true(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "4", include_optional_pack=False)
        steps = self._snapshot_steps(db, work_order_id)
        steps[0].execution_status = "DONE"
        steps[1].execution_status = "DONE"
        db.commit()

        read = build_work_order_routing_execution_read(db=db, work_order_id=work_order_id)

        self.assertTrue(read.is_routing_completed)
        self.assertFalse(read.has_active_step)

    def test_optional_pending_does_not_block_routing_completed(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "5")
        steps = self._snapshot_steps(db, work_order_id)
        steps[0].execution_status = "DONE"
        steps[1].execution_status = "DONE"
        steps[2].execution_status = "PENDING"
        db.commit()

        read = build_work_order_routing_execution_read(db=db, work_order_id=work_order_id)

        self.assertTrue(read.is_routing_completed)
        self.assertEqual(read.steps[2].step_status, "PENDING")

    def test_multiple_active_rows_hard_rejects_with_409(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "6")
        steps = self._snapshot_steps(db, work_order_id)
        steps[0].execution_status = "ACTIVE"
        steps[1].execution_status = "ACTIVE"
        db.commit()

        with self.assertRaises(HTTPException) as exc:
            build_work_order_routing_execution_read(db=db, work_order_id=work_order_id)

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            f"WorkOrder routing snapshot has multiple ACTIVE steps: snapshot_id={self._snapshot(db, work_order_id).id}",
        )

    def test_missing_snapshot_and_missing_work_order_remain_aligned_with_existing_errors(self) -> None:
        db = self._new_db()

        with self.assertRaises(HTTPException) as missing_work_order:
            build_work_order_routing_execution_read(db=db, work_order_id=999)

        self.assertEqual(missing_work_order.exception.status_code, 404)
        self.assertEqual(missing_work_order.exception.detail, "WorkOrder not found: id=999")

        sales_order = _add_sales_order(db, "SO-READX-NO-7")
        product = _add_product(db, "FG-READX-NO-7")
        line = _add_line(db, "LINE-READX-NO-7")
        routing = _add_routing(db, "FG-READX-NO-7")
        _add_step(db, routing.id, 10, "CUT", "Cutting", "Production", True)
        db.commit()
        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no="WO-READX-NO-7",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                planned_hours=2.0,
                priority="NORMAL",
                promise_date=date(2026, 4, 10),
                is_material_ready=False,
            ),
        )
        with self.assertRaises(HTTPException) as missing_snapshot:
            build_work_order_routing_execution_read(db=db, work_order_id=work_order.id)

        self.assertEqual(missing_snapshot.exception.status_code, 409)
        self.assertEqual(
            missing_snapshot.exception.detail,
            f"WorkOrder has no routing snapshot and cannot resolve execution routing authority: id={work_order.id}",
        )

    def test_read_surface_performs_no_writes_after_started_and_completed_rows_exist(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "8")
        guard_work_order_routing_snapshot_active_step(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=10,
            target_seq_no=20,
            active_seq_no=20,
            started_by="operator-a",
        )
        guard_work_order_routing_snapshot_active_step_release(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=20,
            target_seq_no=20,
            release_seq_no=20,
            completed_by="operator-b",
        )
        before = [
            (row.id, row.execution_status, row.started_at, row.started_by, row.completed_at, row.completed_by)
            for row in self._snapshot_steps(db, work_order_id)
        ]

        read = build_work_order_routing_execution_read(db=db, work_order_id=work_order_id)

        self.assertEqual(read.steps[1].step_status, "DONE")
        after = [
            (row.id, row.execution_status, row.started_at, row.started_by, row.completed_at, row.completed_by)
            for row in self._snapshot_steps(db, work_order_id)
        ]
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
