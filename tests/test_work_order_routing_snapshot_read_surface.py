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


class WorkOrderRoutingSnapshotReadSurfaceTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def test_work_order_read_exposes_separate_live_definition_and_frozen_snapshot(self) -> None:
        db = self._new_db()
        sales_order = _add_sales_order(db, "SO-SR-1")
        product = _add_product(db, "FG-SR-1")
        line = _add_line(db, "LINE-SR-1")
        routing = _add_routing(db, "FG-SR-1")
        live_step = _add_step(db, routing.id, 20, "PACK", "Packing", "Packing", False)
        frozen_step = _add_step(db, routing.id, 10, "ASSY", "Assembly", "Production", True)
        db.commit()

        create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no="WO-SR-1",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                routing_id=routing.id,
                planned_hours=4.0,
                priority="NORMAL",
                promise_date=date(2026, 3, 29),
                is_material_ready=True,
            ),
        )

        routing.routing_code = "R-FG-SR-1-LIVE"
        routing.routing_name = "Routing FG-SR-1 Live"
        live_step.step_name = "Packing Live"
        frozen_step.department = "Production Live"
        _add_step(db, routing.id, 30, "QC", "QC Check", "Quality", True)
        db.commit()

        rows = list_work_order_reads(db=db)
        self.assertEqual(len(rows), 1)
        row = rows[0]

        self.assertIsNotNone(row.routing_definition)
        self.assertIsNotNone(row.routing_snapshot)

        self.assertEqual(row.routing_definition.routing_id, routing.id)
        self.assertEqual(row.routing_definition.routing_code, "R-FG-SR-1-LIVE")
        self.assertEqual(row.routing_definition.routing_name, "Routing FG-SR-1 Live")
        self.assertEqual(
            [(step.seq_no, step.step_code, step.step_name, step.department, step.is_required) for step in row.routing_definition.steps],
            [
                (10, "ASSY", "Assembly", "Production Live", True),
                (20, "PACK", "Packing Live", "Packing", False),
                (30, "QC", "QC Check", "Quality", True),
            ],
        )

        self.assertEqual(row.routing_snapshot.source_routing_id, routing.id)
        self.assertEqual(row.routing_snapshot.routing_code, "R-FG-SR-1")
        self.assertEqual(row.routing_snapshot.routing_name, "Routing FG-SR-1")
        self.assertEqual(
            [(step.seq_no, step.step_code, step.step_name, step.department, step.is_required) for step in row.routing_snapshot.steps],
            [
                (10, "ASSY", "Assembly", "Production", True),
                (20, "PACK", "Packing", "Packing", False),
            ],
        )

        snapshot_payload = row.routing_snapshot.model_dump()
        self.assertEqual(
            set(snapshot_payload.keys()),
            {"snapshot_id", "source_routing_id", "routing_code", "routing_name", "steps"},
        )
        self.assertEqual(
            set(snapshot_payload["steps"][0].keys()),
            {"seq_no", "step_code", "step_name", "department", "is_required"},
        )

    def test_work_order_read_keeps_snapshot_surface_empty_without_created_snapshot(self) -> None:
        db = self._new_db()
        sales_order = _add_sales_order(db, "SO-SR-2")
        product = _add_product(db, "FG-SR-2")
        line = _add_line(db, "LINE-SR-2")
        db.commit()

        create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no="WO-SR-2",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                planned_hours=2.0,
                priority="NORMAL",
                promise_date=date(2026, 3, 30),
                is_material_ready=False,
            ),
        )

        rows = list_work_order_reads(db=db)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].routing_snapshot)


if __name__ == "__main__":
    unittest.main()
