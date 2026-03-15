from __future__ import annotations

from datetime import date
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database import Base
from models import Product, ProductionLine, RoutingHeader, RoutingStep, SalesOrder, WorkOrder, WorkOrderRoutingSnapshot
from schemas import WorkOrderCreate
from app.api.v2.work_order_routing_bind import work_order_routing_bind
from app.schemas.work_order_routing_bind import WorkOrderRoutingBindRequest
from app.services.work_order_mainline import create_work_order_record
from app.services.work_order_routing_step_active import guard_work_order_routing_snapshot_active_step
from app.services.work_order_routing_step_active_release import (
    guard_work_order_routing_snapshot_active_step_release,
)


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


class WorkOrderRoutingStepActiveReleaseTests(unittest.TestCase):
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
        sales_order = _add_sales_order(db, f"SO-REL-{suffix}")
        product = _add_product(db, f"FG-REL-{suffix}")
        line = _add_line(db, f"LINE-REL-{suffix}")
        routing = _add_routing(db, f"FG-REL-{suffix}")
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
                work_order_no=f"WO-REL-{suffix}",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                routing_id=routing.id if include_snapshot else None,
                planned_hours=4.0,
                priority="NORMAL",
                promise_date=date(2026, 4, 7),
                is_material_ready=True if include_snapshot else False,
            ),
        )

        if not include_snapshot:
            work_order_routing_bind(
                payload=WorkOrderRoutingBindRequest(work_order_id=work_order.id, routing_id=routing.id),
                db=db,
            )

        return work_order.id

    def _get_snapshot(self, db: Session, work_order_id: int) -> WorkOrderRoutingSnapshot:
        work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
        assert work_order is not None
        assert work_order.routing_snapshot is not None
        return work_order.routing_snapshot

    def test_explicit_release_target_valid_current_active_and_completion_ready_pass(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "1")

        guard_work_order_routing_snapshot_active_step(
            db=db,
            work_order_id=work_order_id,
            current_step_code="ASSY",
            target_step_code="ASSY",
            active_step_code="ASSY",
        )

        release = guard_work_order_routing_snapshot_active_step_release(
            db=db,
            work_order_id=work_order_id,
            current_step_code="ASSY",
            target_step_code="ASSY",
            release_step_code="ASSY",
        )

        self.assertEqual(release.release_target_step.seq_no, 20)
        self.assertEqual(release.current_active_step.seq_no, 20)
        self.assertTrue(release.release_allowed)
        self.assertIsNone(release.resulting_active_step)
        self.assertFalse(release.has_active_step)

    def test_release_pass_confirms_no_active_and_no_auto_next_step(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "2")

        guard_work_order_routing_snapshot_active_step(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=20,
            target_seq_no=20,
            active_seq_no=20,
        )

        release = guard_work_order_routing_snapshot_active_step_release(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=20,
            target_seq_no=20,
            release_seq_no=20,
        )

        self.assertIsNone(release.resulting_active_step)
        self.assertFalse(release.has_active_step)
        self.assertEqual(release.release_target_step.seq_no, 20)
        self.assertNotEqual(release.release_target_step.seq_no, 30)

    def test_omitted_release_target_locator_is_rejected(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "3")

        with self.assertRaises(HTTPException) as exc:
            guard_work_order_routing_snapshot_active_step_release(
                db=db,
                work_order_id=work_order_id,
                current_seq_no=20,
                target_seq_no=20,
                active_seq_no=20,
                existing_active_seq_no=20,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(exc.exception.detail, "active step release target must be explicit")

    def test_invalid_release_target_passes_through_step_28(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "4")

        with self.assertRaises(HTTPException) as exc:
            guard_work_order_routing_snapshot_active_step_release(
                db=db,
                work_order_id=work_order_id,
                current_seq_no=20,
                target_seq_no=20,
                release_step_code="QC",
                active_seq_no=20,
                existing_active_seq_no=20,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder routing step target is not execution-eligible: step_code not found in snapshot_id=1: step_code=QC",
        )

    def test_malformed_snapshot_passes_through_step_27(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "5")
        snapshot = self._get_snapshot(db, work_order_id)
        snapshot.steps[1].seq_no = snapshot.steps[0].seq_no
        db.commit()

        with self.assertRaises(HTTPException) as exc:
            guard_work_order_routing_snapshot_active_step_release(
                db=db,
                work_order_id=work_order_id,
                current_seq_no=20,
                target_seq_no=20,
                release_seq_no=20,
                active_seq_no=20,
                existing_active_seq_no=20,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            f"WorkOrder routing snapshot is not execution-ready: duplicate seq_no=10 in snapshot_id={snapshot.id}",
        )

    def test_release_target_fails_completion_ready_passes_through_step_30(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "6")

        with self.assertRaises(HTTPException) as exc:
            guard_work_order_routing_snapshot_active_step_release(
                db=db,
                work_order_id=work_order_id,
                current_seq_no=10,
                target_seq_no=20,
                release_seq_no=30,
                active_seq_no=20,
                existing_active_seq_no=20,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder routing step completion is not allowed: completion target does not match resolved transition target in snapshot_id=1: target_seq_no=20, completion_seq_no=30",
        )

    def test_current_active_invalid_passes_through_step_32(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "7")

        guard_work_order_routing_snapshot_active_step(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=10,
            target_seq_no=10,
            active_seq_no=10,
        )

        with self.assertRaises(HTTPException) as exc:
            guard_work_order_routing_snapshot_active_step_release(
                db=db,
                work_order_id=work_order_id,
                current_seq_no=20,
                target_seq_no=20,
                release_seq_no=20,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(exc.exception.detail, "active step release target does not match current active step")

    def test_release_target_different_from_current_active_is_rejected(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "8")

        with self.assertRaises(HTTPException) as exc:
            guard_work_order_routing_snapshot_active_step_release(
                db=db,
                work_order_id=work_order_id,
                current_seq_no=20,
                target_seq_no=20,
                release_seq_no=20,
                active_seq_no=10,
                existing_active_seq_no=10,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(exc.exception.detail, "active step release target does not match current active step")

    def test_non_unique_release_target_passes_through_step_28(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(
            db,
            "9",
            steps=[
                (10, "ASSY", "Assembly A", "Production", True),
                (20, "ASSY", "Assembly B", "Production", False),
            ],
        )

        with self.assertRaises(HTTPException) as exc:
            guard_work_order_routing_snapshot_active_step_release(
                db=db,
                work_order_id=work_order_id,
                current_seq_no=10,
                target_seq_no=10,
                release_step_code="ASSY",
                active_seq_no=10,
                existing_active_seq_no=10,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder routing step target is not execution-eligible: step_code resolves to multiple snapshot steps in snapshot_id=1: step_code=ASSY",
        )

    def test_missing_snapshot_passes_through_step_27(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "10", include_snapshot=False)

        with self.assertRaises(HTTPException) as exc:
            guard_work_order_routing_snapshot_active_step_release(
                db=db,
                work_order_id=work_order_id,
                current_step_code="ASSY",
                target_step_code="ASSY",
                release_step_code="ASSY",
                active_step_code="ASSY",
                existing_active_step_code="ASSY",
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            f"WorkOrder has no routing snapshot and cannot resolve execution routing authority: id={work_order_id}",
        )

    def test_snapshot_missing_step_field_passes_through_step_27(self) -> None:
        db = self._new_db()
        work_order_id = self._create_work_order_with_snapshot(db, "11")
        snapshot = self._get_snapshot(db, work_order_id)
        snapshot.steps[1].step_code = ""
        db.commit()

        with self.assertRaises(HTTPException) as exc:
            guard_work_order_routing_snapshot_active_step_release(
                db=db,
                work_order_id=work_order_id,
                current_seq_no=20,
                target_seq_no=20,
                release_seq_no=20,
                active_seq_no=20,
                existing_active_seq_no=20,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            f"WorkOrder routing snapshot is not execution-ready: snapshot step missing step_code: snapshot_id={snapshot.id}, step_id={snapshot.steps[1].id}",
        )


if __name__ == "__main__":
    unittest.main()
