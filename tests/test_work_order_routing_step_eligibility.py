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
from app.services.work_order_routing_step_eligibility import resolve_work_order_execution_eligible_routing_step


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


class WorkOrderRoutingStepEligibilityTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def _create_work_order_with_snapshot(self, db: Session, suffix: str) -> tuple[int, int]:
        sales_order = _add_sales_order(db, f"SO-ELIG-{suffix}")
        product = _add_product(db, f"FG-ELIG-{suffix}")
        line = _add_line(db, f"LINE-ELIG-{suffix}")
        routing = _add_routing(db, f"FG-ELIG-{suffix}")
        _add_step(db, routing.id, 10, "ASSY", "Assembly", "Production", True)
        _add_step(db, routing.id, 20, "PACK", "Packing", "Packing", False)
        db.commit()

        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no=f"WO-ELIG-{suffix}",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                routing_id=routing.id,
                planned_hours=4.0,
                priority="NORMAL",
                promise_date=date(2026, 4, 2),
                is_material_ready=True,
            ),
        )
        return work_order.id, routing.id

    def test_step_code_resolves_one_eligible_snapshot_step(self) -> None:
        db = self._new_db()
        work_order_id, routing_id = self._create_work_order_with_snapshot(db, "1")

        eligible_step = resolve_work_order_execution_eligible_routing_step(
            db=db,
            work_order_id=work_order_id,
            step_code="PACK",
        )

        self.assertEqual(eligible_step.work_order_id, work_order_id)
        self.assertEqual(eligible_step.snapshot_id, list_work_order_reads(db=db)[0].routing_snapshot.snapshot_id)
        self.assertEqual(eligible_step.seq_no, 20)
        self.assertEqual(eligible_step.step_code, "PACK")
        self.assertEqual(eligible_step.step_name, "Packing")
        self.assertEqual(eligible_step.department, "Packing")
        self.assertFalse(eligible_step.is_required)
        self.assertEqual(list_work_order_reads(db=db)[0].routing_snapshot.source_routing_id, routing_id)

    def test_seq_no_resolves_one_eligible_snapshot_step(self) -> None:
        db = self._new_db()
        work_order_id, _ = self._create_work_order_with_snapshot(db, "2")

        eligible_step = resolve_work_order_execution_eligible_routing_step(
            db=db,
            work_order_id=work_order_id,
            seq_no=10,
        )

        self.assertEqual(
            (eligible_step.seq_no, eligible_step.step_code, eligible_step.step_name, eligible_step.department, eligible_step.is_required),
            (10, "ASSY", "Assembly", "Production", True),
        )

    def test_step_code_and_seq_no_resolve_one_eligible_snapshot_step(self) -> None:
        db = self._new_db()
        work_order_id, _ = self._create_work_order_with_snapshot(db, "3")

        eligible_step = resolve_work_order_execution_eligible_routing_step(
            db=db,
            work_order_id=work_order_id,
            step_code="ASSY",
            seq_no=10,
        )

        self.assertEqual(
            (eligible_step.seq_no, eligible_step.step_code, eligible_step.step_name, eligible_step.department, eligible_step.is_required),
            (10, "ASSY", "Assembly", "Production", True),
        )

    def test_absent_step_identifiers_are_rejected(self) -> None:
        db = self._new_db()
        work_order_id, _ = self._create_work_order_with_snapshot(db, "4")

        with self.assertRaises(HTTPException) as exc:
            resolve_work_order_execution_eligible_routing_step(db=db, work_order_id=work_order_id)

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            f"WorkOrder routing step target is not execution-eligible: step_code and seq_no are both absent for work_order_id={work_order_id}",
        )

    def test_unknown_step_code_is_rejected(self) -> None:
        db = self._new_db()
        work_order_id, _ = self._create_work_order_with_snapshot(db, "5")

        with self.assertRaises(HTTPException) as exc:
            resolve_work_order_execution_eligible_routing_step(
                db=db,
                work_order_id=work_order_id,
                step_code="QC",
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder routing step target is not execution-eligible: step_code not found in snapshot_id=1: step_code=QC",
        )

    def test_unknown_seq_no_is_rejected(self) -> None:
        db = self._new_db()
        work_order_id, _ = self._create_work_order_with_snapshot(db, "6")

        with self.assertRaises(HTTPException) as exc:
            resolve_work_order_execution_eligible_routing_step(
                db=db,
                work_order_id=work_order_id,
                seq_no=30,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder routing step target is not execution-eligible: seq_no not found in snapshot_id=1: seq_no=30",
        )

    def test_mismatched_step_code_and_seq_no_are_rejected(self) -> None:
        db = self._new_db()
        work_order_id, _ = self._create_work_order_with_snapshot(db, "7")

        with self.assertRaises(HTTPException) as exc:
            resolve_work_order_execution_eligible_routing_step(
                db=db,
                work_order_id=work_order_id,
                step_code="PACK",
                seq_no=10,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder routing step target is not execution-eligible: step_code and seq_no do not identify the same snapshot step in snapshot_id=1: step_code=PACK, seq_no=10",
        )

    def test_non_unique_step_code_resolution_is_rejected(self) -> None:
        db = self._new_db()
        sales_order = _add_sales_order(db, "SO-ELIG-8")
        product = _add_product(db, "FG-ELIG-8")
        line = _add_line(db, "LINE-ELIG-8")
        routing = _add_routing(db, "FG-ELIG-8")
        _add_step(db, routing.id, 10, "ASSY", "Assembly A", "Production", True)
        _add_step(db, routing.id, 20, "ASSY", "Assembly B", "Production", False)
        db.commit()

        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no="WO-ELIG-8",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                routing_id=routing.id,
                planned_hours=4.0,
                priority="NORMAL",
                promise_date=date(2026, 4, 2),
                is_material_ready=True,
            ),
        )

        with self.assertRaises(HTTPException) as exc:
            resolve_work_order_execution_eligible_routing_step(
                db=db,
                work_order_id=work_order.id,
                step_code="ASSY",
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder routing step target is not execution-eligible: step_code resolves to multiple snapshot steps in snapshot_id=1: step_code=ASSY",
        )

    def test_step_code_and_seq_no_can_resolve_unique_step_when_step_code_is_not_unique(self) -> None:
        db = self._new_db()
        sales_order = _add_sales_order(db, "SO-ELIG-8B")
        product = _add_product(db, "FG-ELIG-8B")
        line = _add_line(db, "LINE-ELIG-8B")
        routing = _add_routing(db, "FG-ELIG-8B")
        _add_step(db, routing.id, 10, "ASSY", "Assembly A", "Production", True)
        _add_step(db, routing.id, 20, "ASSY", "Assembly B", "Production", False)
        db.commit()

        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no="WO-ELIG-8B",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                routing_id=routing.id,
                planned_hours=4.0,
                priority="NORMAL",
                promise_date=date(2026, 4, 2),
                is_material_ready=True,
            ),
        )

        eligible_step = resolve_work_order_execution_eligible_routing_step(
            db=db,
            work_order_id=work_order.id,
            step_code="ASSY",
            seq_no=20,
        )

        self.assertEqual(
            (eligible_step.seq_no, eligible_step.step_code, eligible_step.step_name, eligible_step.department, eligible_step.is_required),
            (20, "ASSY", "Assembly B", "Production", False),
        )

    def test_missing_snapshot_remains_rejected_through_step_eligibility_path(self) -> None:
        db = self._new_db()
        sales_order = _add_sales_order(db, "SO-ELIG-9")
        product = _add_product(db, "FG-ELIG-9")
        line = _add_line(db, "LINE-ELIG-9")
        routing = _add_routing(db, "FG-ELIG-9")
        _add_step(db, routing.id, 10, "ASSY", "Assembly", "Production", True)
        db.commit()

        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no="WO-ELIG-9",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                planned_hours=2.0,
                priority="NORMAL",
                promise_date=date(2026, 4, 2),
                is_material_ready=False,
            ),
        )

        work_order_routing_bind(
            payload=WorkOrderRoutingBindRequest(work_order_id=work_order.id, routing_id=routing.id),
            db=db,
        )

        with self.assertRaises(HTTPException) as exc:
            resolve_work_order_execution_eligible_routing_step(
                db=db,
                work_order_id=work_order.id,
                step_code="ASSY",
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            f"WorkOrder has no routing snapshot and cannot resolve execution routing authority: id={work_order.id}",
        )

    def test_missing_work_order_remains_rejected_through_step_eligibility_path(self) -> None:
        db = self._new_db()

        with self.assertRaises(HTTPException) as exc:
            resolve_work_order_execution_eligible_routing_step(
                db=db,
                work_order_id=999,
                step_code="ASSY",
            )

        self.assertEqual(exc.exception.status_code, 404)
        self.assertEqual(exc.exception.detail, "WorkOrder not found: id=999")


if __name__ == "__main__":
    unittest.main()
