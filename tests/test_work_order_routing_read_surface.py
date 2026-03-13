from __future__ import annotations

from datetime import date
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database import Base
from models import Product, ProductionLine, RoutingHeader, RoutingStep, SalesOrder
from schemas import WorkOrderCreate
from app.services.work_order_mainline import create_work_order_record, list_work_order_reads


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


class WorkOrderRoutingReadSurfaceTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def test_work_order_read_exposes_minimal_definition_only_routing_surface(self) -> None:
        db = self._new_db()
        sales_order = _add_sales_order(db, "SO-RD-1")
        product = _add_product(db, "FG-READ-1")
        line = _add_line(db, "LINE-RD-1")
        routing = _add_routing(db, "FG-READ-1")
        _add_step(db, routing.id, 20, "PACK", "Packing", "Packing", False)
        _add_step(db, routing.id, 10, "ASSY", "Assembly", "Production", True)
        db.commit()

        create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no="WO-READ-1",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                routing_id=routing.id,
                planned_hours=4.0,
                priority="NORMAL",
                promise_date=date(2026, 3, 25),
                is_material_ready=True,
            ),
        )

        rows = list_work_order_reads(db=db)
        self.assertEqual(len(rows), 1)

        row = rows[0]
        self.assertEqual(row.routing_id, routing.id)
        self.assertIsNotNone(row.routing_definition)
        self.assertEqual(row.routing_definition.routing_id, routing.id)
        self.assertEqual(row.routing_definition.routing_code, f"R-{product.model_no}")
        self.assertEqual(row.routing_definition.routing_name, f"Routing {product.model_no}")
        self.assertEqual(row.routing_definition.routing_status, "ACTIVE")
        self.assertEqual(
            [
                (step.seq_no, step.step_code, step.step_name, step.department, step.is_required)
                for step in row.routing_definition.steps
            ],
            [
                (10, "ASSY", "Assembly", "Production", True),
                (20, "PACK", "Packing", "Packing", False),
            ],
        )

        routing_payload = row.routing_definition.model_dump()
        self.assertEqual(set(routing_payload.keys()), {"routing_id", "routing_code", "routing_name", "routing_status", "steps"})
        self.assertEqual(
            set(routing_payload["steps"][0].keys()),
            {"seq_no", "step_code", "step_name", "department", "is_required"},
        )

    def test_work_order_read_keeps_unbound_work_order_routing_surface_empty(self) -> None:
        db = self._new_db()
        sales_order = _add_sales_order(db, "SO-RD-2")
        product = _add_product(db, "FG-READ-2")
        line = _add_line(db, "LINE-RD-2")
        db.commit()

        create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no="WO-READ-2",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                planned_hours=2.0,
                priority="NORMAL",
                promise_date=date(2026, 3, 26),
                is_material_ready=False,
            ),
        )

        rows = list_work_order_reads(db=db)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].routing_id)
        self.assertIsNone(rows[0].routing_definition)


if __name__ == "__main__":
    unittest.main()
