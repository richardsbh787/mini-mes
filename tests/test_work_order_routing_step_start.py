from __future__ import annotations

from datetime import date
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database import Base
from models import Product, ProductionLine, RoutingHeader, RoutingStep, SalesOrder
from schemas import WorkOrderCreate
from app.api.v2.work_order_routing_bind import work_order_routing_bind
from app.schemas.work_order_routing_bind import WorkOrderRoutingBindRequest
from app.services.work_order_mainline import create_work_order_record, list_work_order_reads
from app.services.work_order_routing_step_start import validate_work_order_execution_start_ready_routing_step


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
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


class WorkOrderRoutingStepStartTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def _create_work_order_with_snapshot(
        self,
        db: Session,
        suffix: str,
        *,
        steps: list[tuple[int, str, str, str, bool]] | None = None,
        include_snapshot: bool = True,
    ) -> int:
        sales_order = _add_sales_order(db, f"SO-START-{suffix}")
        product = _add_product(db, f"FG-START-{suffix}")
        line = _add_line(db, f"LINE-START-{suffix}")
        routing = _add_routing(db, f"FG-START-{suffix}")
        for seq_no, step_code, step_name, department, is_required in (
            steps
            if steps is not None
            else [
                (10, "CUT", "Cutting", "Production", True),
                (20, "ASSY", "Assembly", "Production", True),
                (30, "PACK", "Packing", "Packing", False),
            ]
        ):
            _add_step(db, routing.id, seq_no, step_code, step_name, department, is_required)
        db.commit()

        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no=f"WO-START-{suffix}",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                routing_id=routing.id if include_snapshot else None,
                planned_hours=4.0,
                priority="NORMAL",
                promise_date=date(2026, 4, 5),
                is_material_ready=True if include_snapshot else False,
            ),
        )

        if not include_snapshot:
            work_order_routing_bind(
                payload=WorkOrderRoutingBindRequest(work_order_id=work_order.id, routing_id=routing.id),
                db=db,
            )

        return work_order.id

    def test_same_step_start_readiness_is_allowed(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "1")

        start = validate_work_order_execution_start_ready_routing_step(
            db=db,
            work_order_id=work_order_id,
            current_step_code="ASSY",
            target_step_code="ASSY",
        )

        self.assertEqual(start.current_step.seq_no, 20)
        self.assertEqual(start.target_step.seq_no, 20)
        self.assertEqual(start.start_step.seq_no, 20)
        self.assertEqual(start.snapshot_id, list_work_order_reads(db=db)[0].routing_snapshot.snapshot_id)

    def test_forward_target_start_readiness_is_allowed(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "2")

        start = validate_work_order_execution_start_ready_routing_step(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=10,
            target_seq_no=20,
        )

        self.assertEqual(
            (start.current_step.seq_no, start.target_step.seq_no, start.start_step.seq_no),
            (10, 20, 20),
        )

    def test_invalid_target_step_is_rejected(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "3")

        with self.assertRaises(HTTPException) as exc:
            validate_work_order_execution_start_ready_routing_step(
                db=db,
                work_order_id=work_order_id,
                current_step_code="ASSY",
                target_step_code="QC",
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder routing step transition is not allowed: invalid target step target: WorkOrder routing step target is not execution-eligible: step_code not found in snapshot_id=1: step_code=QC",
        )

    def test_invalid_transition_is_rejected(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "4")

        with self.assertRaises(HTTPException) as exc:
            validate_work_order_execution_start_ready_routing_step(
                db=db,
                work_order_id=work_order_id,
                current_seq_no=10,
                target_seq_no=30,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder routing step transition is not allowed: forward transition skips required snapshot step(s) in snapshot_id=1: skipped_seq_no=20",
        )

    def test_start_target_mismatch_is_rejected(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "5")

        with self.assertRaises(HTTPException) as exc:
            validate_work_order_execution_start_ready_routing_step(
                db=db,
                work_order_id=work_order_id,
                current_seq_no=10,
                target_seq_no=20,
                start_seq_no=30,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder routing step start is not allowed: start target does not match resolved transition target in snapshot_id=1: target_seq_no=20, start_seq_no=30",
        )

    def test_missing_snapshot_remains_rejected_through_start_path(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "6", include_snapshot=False)

        with self.assertRaises(HTTPException) as exc:
            validate_work_order_execution_start_ready_routing_step(
                db=db,
                work_order_id=work_order_id,
                current_step_code="CUT",
                target_step_code="ASSY",
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            f"WorkOrder has no routing snapshot and cannot resolve execution routing authority: id={work_order_id}",
        )

    def test_missing_work_order_remains_rejected_through_start_path(self) -> None:
        db = self._new_db()

        with self.assertRaises(HTTPException) as exc:
            validate_work_order_execution_start_ready_routing_step(
                db=db,
                work_order_id=999,
                current_step_code="CUT",
                target_step_code="ASSY",
            )

        self.assertEqual(exc.exception.status_code, 404)
        self.assertEqual(exc.exception.detail, "WorkOrder not found: id=999")


if __name__ == "__main__":
    unittest.main()
