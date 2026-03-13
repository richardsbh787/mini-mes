from __future__ import annotations

from datetime import date
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database import Base
from models import (
    Product,
    ProductionLine,
    RoutingHeader,
    RoutingStep,
    SalesOrder,
    WorkOrderRoutingSnapshot,
    WorkOrderRoutingSnapshotStep,
)
from schemas import WorkOrderCreate
from app.api.v2.work_order_routing_bind import work_order_routing_bind
from app.schemas.work_order_routing_bind import WorkOrderRoutingBindRequest
from app.services.work_order_mainline import create_work_order_record


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


class WorkOrderRoutingSnapshotTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def test_work_order_creation_with_routing_creates_frozen_snapshot(self) -> None:
        db = self._new_db()
        sales_order = _add_sales_order(db, "SO-SNAP-1")
        product = _add_product(db, "FG-SNAP-1")
        line = _add_line(db, "LINE-SNAP-1")
        routing = _add_routing(db, "FG-SNAP-1")
        step_a = _add_step(db, routing.id, 20, "PACK", "Packing", "Packing", False)
        step_b = _add_step(db, routing.id, 10, "ASSY", "Assembly", "Production", True)
        db.commit()

        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no="WO-SNAP-1",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                routing_id=routing.id,
                planned_hours=4.0,
                priority="NORMAL",
                promise_date=date(2026, 3, 27),
                is_material_ready=True,
            ),
        )

        snapshot = (
            db.query(WorkOrderRoutingSnapshot)
            .filter(WorkOrderRoutingSnapshot.work_order_id == work_order.id)
            .one()
        )
        steps = (
            db.query(WorkOrderRoutingSnapshotStep)
            .filter(WorkOrderRoutingSnapshotStep.snapshot_id == snapshot.id)
            .order_by(WorkOrderRoutingSnapshotStep.seq_no.asc(), WorkOrderRoutingSnapshotStep.id.asc())
            .all()
        )

        self.assertEqual(snapshot.source_routing_id, routing.id)
        self.assertEqual(snapshot.routing_code, routing.routing_code)
        self.assertEqual(snapshot.routing_name, routing.routing_name)
        self.assertEqual(
            [(step.seq_no, step.step_code, step.step_name, step.department, step.is_required) for step in steps],
            [
                (10, "ASSY", "Assembly", "Production", True),
                (20, "PACK", "Packing", "Packing", False),
            ],
        )

        routing.routing_code = "R-FG-SNAP-1-NEW"
        routing.routing_name = "Routing FG-SNAP-1 Edited"
        step_a.step_name = "Packing Edited"
        step_b.department = "Prod Edited"
        _add_step(db, routing.id, 30, "QC", "QC Check", "Quality", True)
        db.commit()

        frozen_snapshot = db.query(WorkOrderRoutingSnapshot).filter(WorkOrderRoutingSnapshot.id == snapshot.id).one()
        frozen_steps = (
            db.query(WorkOrderRoutingSnapshotStep)
            .filter(WorkOrderRoutingSnapshotStep.snapshot_id == snapshot.id)
            .order_by(WorkOrderRoutingSnapshotStep.seq_no.asc(), WorkOrderRoutingSnapshotStep.id.asc())
            .all()
        )
        self.assertEqual(frozen_snapshot.routing_code, f"R-{product.model_no}")
        self.assertEqual(frozen_snapshot.routing_name, f"Routing {product.model_no}")
        self.assertEqual(
            [(step.seq_no, step.step_code, step.step_name, step.department, step.is_required) for step in frozen_steps],
            [
                (10, "ASSY", "Assembly", "Production", True),
                (20, "PACK", "Packing", "Packing", False),
            ],
        )

    def test_later_routing_bind_does_not_backfill_snapshot(self) -> None:
        db = self._new_db()
        sales_order = _add_sales_order(db, "SO-SNAP-2")
        product = _add_product(db, "FG-SNAP-2")
        line = _add_line(db, "LINE-SNAP-2")
        routing = _add_routing(db, "FG-SNAP-2")
        _add_step(db, routing.id, 10, "ASSY", "Assembly", "Production", True)
        db.commit()

        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no="WO-SNAP-2",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                planned_hours=2.0,
                priority="NORMAL",
                promise_date=date(2026, 3, 28),
                is_material_ready=False,
            ),
        )

        self.assertEqual(
            db.query(WorkOrderRoutingSnapshot)
            .filter(WorkOrderRoutingSnapshot.work_order_id == work_order.id)
            .count(),
            0,
        )

        work_order_routing_bind(
            payload=WorkOrderRoutingBindRequest(work_order_id=work_order.id, routing_id=routing.id),
            db=db,
        )

        self.assertEqual(
            db.query(WorkOrderRoutingSnapshot)
            .filter(WorkOrderRoutingSnapshot.work_order_id == work_order.id)
            .count(),
            0,
        )


if __name__ == "__main__":
    unittest.main()
