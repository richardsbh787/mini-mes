from __future__ import annotations

from datetime import date
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database import Base
from main import create_work_order
from models import Product, ProductionLine, RoutingHeader, RoutingStep, SalesOrder, WorkOrder
from schemas import WorkOrderCreate
from app.api.v2.work_order_routing_bind import work_order_routing_bind
from app.schemas.work_order_routing_bind import WorkOrderRoutingBindRequest


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def _add_sales_order(db: Session) -> SalesOrder:
    row = SalesOrder(
        order_no="SO-100",
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


def _add_line(db: Session) -> ProductionLine:
    row = ProductionLine(
        line_name="LINE-1",
        working_hours_per_day=8.0,
        efficiency_rate=1.0,
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def _add_routing_header(db: Session, item_code: str, status: str = "ACTIVE") -> RoutingHeader:
    row = RoutingHeader(
        item_code=item_code,
        routing_code=f"R-{item_code}",
        routing_name=f"Routing {item_code}",
        status=status,
    )
    db.add(row)
    db.flush()
    return row


def _add_routing_step(
    db: Session,
    routing_id: int,
    seq_no: int,
    step_code: str = "ASSY",
    step_name: str = "Assembly",
    is_required: bool = True,
) -> RoutingStep:
    row = RoutingStep(
        routing_id=routing_id,
        seq_no=seq_no,
        step_code=step_code,
        step_name=step_name,
        department="Production",
        is_required=is_required,
    )
    db.add(row)
    db.flush()
    return row


class WorkOrderRoutingBindingTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def _seed_work_order_prereqs(self, db: Session, model_no: str = "FG-100") -> tuple[SalesOrder, Product, ProductionLine]:
        return _add_sales_order(db), _add_product(db, model_no), _add_line(db)

    def test_create_work_order_accepts_active_matching_routing_reference(self) -> None:
        db = self._new_db()
        sales_order, product, line = self._seed_work_order_prereqs(db, model_no="FG-100")
        routing = _add_routing_header(db, item_code="FG-100", status="ACTIVE")
        _add_routing_step(db, routing_id=routing.id, seq_no=10)
        db.commit()

        row = create_work_order(
            work_order=WorkOrderCreate(
                work_order_no="WO-100",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                routing_id=routing.id,
                planned_hours=5.0,
                priority="NORMAL",
                promise_date=date(2026, 3, 20),
                is_material_ready=False,
            ),
            db=db,
        )

        self.assertEqual(row.routing_id, routing.id)
        stored = db.query(WorkOrder).filter(WorkOrder.id == row.id).one()
        self.assertEqual(stored.routing_id, routing.id)

    def test_create_work_order_rejects_inactive_or_mismatched_or_empty_routing(self) -> None:
        db = self._new_db()
        sales_order, product, line = self._seed_work_order_prereqs(db, model_no="FG-100")

        inactive = _add_routing_header(db, item_code="FG-100", status="INACTIVE")
        _add_routing_step(db, routing_id=inactive.id, seq_no=10)
        mismatch = _add_routing_header(db, item_code="FG-200", status="ACTIVE")
        _add_routing_step(db, routing_id=mismatch.id, seq_no=10)
        empty = _add_routing_header(db, item_code="FG-100", status="ACTIVE")
        db.commit()

        for routing_id, expected_detail in [
            (inactive.id, f"Routing header is not ACTIVE and cannot be bound: id={inactive.id}"),
            (
                mismatch.id,
                "Routing item_code does not match WorkOrder target item: "
                f"routing_id={mismatch.id}, routing_item_code=FG-200, work_order_item_code=FG-100",
            ),
            (empty.id, f"Routing header has no steps and cannot be bound: id={empty.id}"),
        ]:
            with self.assertRaises(HTTPException) as exc:
                create_work_order(
                    work_order=WorkOrderCreate(
                        work_order_no=f"WO-{routing_id}",
                        sales_order_id=sales_order.id,
                        product_id=product.id,
                        production_line_id=line.id,
                        routing_id=routing_id,
                        planned_hours=5.0,
                        priority="NORMAL",
                        promise_date=date(2026, 3, 20),
                        is_material_ready=True,
                    ),
                    db=db,
                )
            self.assertEqual(exc.exception.status_code, 409)
            self.assertEqual(exc.exception.detail, expected_detail)

    def test_work_order_routing_bind_requires_existing_active_valid_routing_and_does_not_mutate_definition(self) -> None:
        db = self._new_db()
        sales_order, product, line = self._seed_work_order_prereqs(db, model_no="FG-500")
        routing = _add_routing_header(db, item_code="FG-500", status="ACTIVE")
        step = _add_routing_step(db, routing_id=routing.id, seq_no=10, step_code="PACK", step_name="Packing")
        db.commit()

        work_order = create_work_order(
            work_order=WorkOrderCreate(
                work_order_no="WO-500",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                planned_hours=3.0,
                priority="NORMAL",
                promise_date=date(2026, 3, 22),
                is_material_ready=True,
            ),
            db=db,
        )

        before_header = db.query(RoutingHeader).filter(RoutingHeader.id == routing.id).one()
        before_step = db.query(RoutingStep).filter(RoutingStep.id == step.id).one()

        bound = work_order_routing_bind(
            payload=WorkOrderRoutingBindRequest(work_order_id=work_order.id, routing_id=routing.id),
            db=db,
        )

        self.assertEqual(bound.routing_id, routing.id)

        after_header = db.query(RoutingHeader).filter(RoutingHeader.id == routing.id).one()
        after_step = db.query(RoutingStep).filter(RoutingStep.id == step.id).one()
        self.assertEqual(after_header.item_code, before_header.item_code)
        self.assertEqual(after_header.routing_code, before_header.routing_code)
        self.assertEqual(after_header.routing_name, before_header.routing_name)
        self.assertEqual(after_header.status, before_header.status)
        self.assertEqual(after_step.seq_no, before_step.seq_no)
        self.assertEqual(after_step.step_code, before_step.step_code)
        self.assertEqual(after_step.step_name, before_step.step_name)
        self.assertEqual(after_step.is_required, before_step.is_required)

    def test_work_order_routing_bind_rejects_missing_work_order_or_invalid_step_sequence(self) -> None:
        db = self._new_db()
        _sales_order, product, _line = self._seed_work_order_prereqs(db, model_no="FG-700")
        routing = _add_routing_header(db, item_code="FG-700", status="ACTIVE")
        db.flush()
        db.add(
            RoutingStep(
                routing_id=routing.id,
                seq_no=0,
                step_code="BAD",
                step_name="Bad Step",
                department="Production",
                is_required=True,
            )
        )
        db.commit()

        with self.assertRaises(HTTPException) as missing_work_order:
            work_order_routing_bind(
                payload=WorkOrderRoutingBindRequest(work_order_id=999, routing_id=routing.id),
                db=db,
            )
        self.assertEqual(missing_work_order.exception.status_code, 404)
        self.assertEqual(missing_work_order.exception.detail, "WorkOrder not found: id=999")

        work_order = WorkOrder(
            work_order_no="WO-700",
            sales_order_id=1,
            product_id=product.id,
            production_line_id=1,
            planned_hours=2.0,
            actual_hours=0.0,
            remaining_hours=2.0,
            priority="NORMAL",
            promise_date=date(2026, 3, 23),
            status="OPEN",
            is_material_ready=True,
        )
        db.add(work_order)
        db.commit()
        db.refresh(work_order)

        with self.assertRaises(HTTPException) as invalid_sequence:
            work_order_routing_bind(
                payload=WorkOrderRoutingBindRequest(work_order_id=work_order.id, routing_id=routing.id),
                db=db,
            )
        self.assertEqual(invalid_sequence.exception.status_code, 409)
        self.assertEqual(
            invalid_sequence.exception.detail,
            f"Routing header has invalid non-positive seq_no and cannot be bound: id={routing.id}",
        )


if __name__ == "__main__":
    unittest.main()
