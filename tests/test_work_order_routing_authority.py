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
from app.services.work_order_routing_authority import resolve_work_order_execution_routing_authority


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


class WorkOrderRoutingAuthorityTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def test_execution_routing_authority_uses_snapshot_not_live_definition(self) -> None:
        db = self._new_db()
        sales_order = _add_sales_order(db, "SO-AUTH-1")
        product = _add_product(db, "FG-AUTH-1")
        line = _add_line(db, "LINE-AUTH-1")
        routing = _add_routing(db, "FG-AUTH-1")
        step_a = _add_step(db, routing.id, 20, "PACK", "Packing", "Packing", False)
        step_b = _add_step(db, routing.id, 10, "ASSY", "Assembly", "Production", True)
        db.commit()

        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no="WO-AUTH-1",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                routing_id=routing.id,
                planned_hours=4.0,
                priority="NORMAL",
                promise_date=date(2026, 3, 31),
                is_material_ready=True,
            ),
        )

        routing.routing_code = "R-FG-AUTH-1-LIVE"
        routing.routing_name = "Routing FG-AUTH-1 Live"
        step_a.step_name = "Packing Live"
        step_b.department = "Production Live"
        _add_step(db, routing.id, 30, "QC", "QC Check", "Quality", True)
        db.commit()

        authority = resolve_work_order_execution_routing_authority(db=db, work_order_id=work_order.id)

        self.assertEqual(authority.work_order_id, work_order.id)
        self.assertEqual(authority.source_routing_id, routing.id)
        self.assertEqual(authority.routing_code, "R-FG-AUTH-1")
        self.assertEqual(authority.routing_name, "Routing FG-AUTH-1")
        self.assertEqual(
            [(step.seq_no, step.step_code, step.step_name, step.department, step.is_required) for step in authority.steps],
            [
                (10, "ASSY", "Assembly", "Production", True),
                (20, "PACK", "Packing", "Packing", False),
            ],
        )

        read_rows = list_work_order_reads(db=db)
        self.assertEqual(read_rows[0].routing_definition.routing_code, "R-FG-AUTH-1-LIVE")
        self.assertEqual(read_rows[0].routing_snapshot.routing_code, "R-FG-AUTH-1")

    def test_execution_routing_authority_does_not_fallback_to_live_routing_without_snapshot(self) -> None:
        db = self._new_db()
        sales_order = _add_sales_order(db, "SO-AUTH-2")
        product = _add_product(db, "FG-AUTH-2")
        line = _add_line(db, "LINE-AUTH-2")
        routing = _add_routing(db, "FG-AUTH-2")
        _add_step(db, routing.id, 10, "ASSY", "Assembly", "Production", True)
        db.commit()

        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no="WO-AUTH-2",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                planned_hours=2.0,
                priority="NORMAL",
                promise_date=date(2026, 4, 1),
                is_material_ready=False,
            ),
        )

        work_order_routing_bind(
            payload=WorkOrderRoutingBindRequest(work_order_id=work_order.id, routing_id=routing.id),
            db=db,
        )

        with self.assertRaises(HTTPException) as exc:
            resolve_work_order_execution_routing_authority(db=db, work_order_id=work_order.id)

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            f"WorkOrder has no routing snapshot and cannot resolve execution routing authority: id={work_order.id}",
        )

    def test_execution_routing_authority_rejects_missing_work_order(self) -> None:
        db = self._new_db()

        with self.assertRaises(HTTPException) as exc:
            resolve_work_order_execution_routing_authority(db=db, work_order_id=999)

        self.assertEqual(exc.exception.status_code, 404)
        self.assertEqual(exc.exception.detail, "WorkOrder not found: id=999")


if __name__ == "__main__":
    unittest.main()
