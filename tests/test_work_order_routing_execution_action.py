from __future__ import annotations

from datetime import date
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker

from app.api.v2.work_order_routing_execution_action import router
from app.bootstrap.work_order_routing_execution_state_schema import ensure_work_order_routing_execution_state_columns
from app.services.work_order_mainline import create_work_order_record
from database import Base, get_db
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


def _make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    ensure_work_order_routing_execution_state_columns(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def _add_sales_order(db: Session, order_no: str) -> SalesOrder:
    row = SalesOrder(
        order_no=order_no,
        customer_name="Test Customer",
        order_date=date(2026, 3, 16),
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


class WorkOrderRoutingExecutionActionApiTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def _new_client(self, db: Session) -> TestClient:
        app = FastAPI()
        app.include_router(router)

        def override_get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        self.addCleanup(client.close)
        return client

    def _create_work_order_with_snapshot(
        self,
        db: Session,
        suffix: str,
        *,
        steps: list[tuple[int, str, str, str, bool]] | None = None,
    ) -> int:
        sales_order = _add_sales_order(db, f"SO-ACTION-{suffix}")
        product = _add_product(db, f"FG-ACTION-{suffix}")
        line = _add_line(db, f"LINE-ACTION-{suffix}")
        routing = _add_routing(db, f"FG-ACTION-{suffix}")
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
                work_order_no=f"WO-ACTION-{suffix}",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                routing_id=routing.id,
                planned_hours=4.0,
                priority="NORMAL",
                promise_date=date(2026, 4, 16),
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

    def test_start_action_writes_active_correctly(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "1")

        response = client.post(
            "/v2/work-order/routing-execution/start",
            json={"work_order_id": work_order_id, "seq_no": 20, "started_by": "operator-a"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["work_order_id"], work_order_id)
        self.assertEqual(payload["execution_status"], "ACTIVE")
        self.assertEqual(payload["affected_step"]["seq_no"], 20)
        self.assertTrue(payload["active_state"]["has_active_step"])
        self.assertEqual(payload["active_state"]["active_step"]["seq_no"], 20)

        steps = self._snapshot_steps(db, work_order_id)
        self.assertEqual([(row.seq_no, row.execution_status) for row in steps], [(10, "PENDING"), (20, "ACTIVE"), (30, "PENDING")])
        self.assertEqual(steps[1].started_by, "operator-a")
        self.assertIsNotNone(steps[1].started_at)

    def test_release_action_writes_done_correctly(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "2")

        start_response = client.post(
            "/v2/work-order/routing-execution/start",
            json={"work_order_id": work_order_id, "step_code": "ASSY", "started_by": "operator-a"},
        )
        self.assertEqual(start_response.status_code, 200)

        response = client.post(
            "/v2/work-order/routing-execution/release",
            json={"work_order_id": work_order_id, "step_code": "ASSY", "completed_by": "operator-b"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["execution_status"], "DONE")
        self.assertEqual(payload["affected_step"]["step_code"], "ASSY")
        self.assertFalse(payload["active_state"]["has_active_step"])
        self.assertIsNone(payload["active_state"]["active_step"])

        steps = self._snapshot_steps(db, work_order_id)
        self.assertEqual([(row.seq_no, row.execution_status) for row in steps], [(10, "PENDING"), (20, "DONE"), (30, "PENDING")])
        self.assertEqual(steps[1].completed_by, "operator-b")
        self.assertIsNotNone(steps[1].completed_at)

    def test_single_active_rule_remains_intact(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "3")

        first = client.post(
            "/v2/work-order/routing-execution/start",
            json={"work_order_id": work_order_id, "seq_no": 10, "started_by": "operator-a"},
        )
        self.assertEqual(first.status_code, 200)

        second = client.post(
            "/v2/work-order/routing-execution/start",
            json={"work_order_id": work_order_id, "seq_no": 20, "started_by": "operator-b"},
        )

        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json()["detail"], "work order already has a different active step")
        steps = self._snapshot_steps(db, work_order_id)
        self.assertEqual([(row.seq_no, row.execution_status) for row in steps], [(10, "ACTIVE"), (20, "PENDING"), (30, "PENDING")])

    def test_release_does_not_auto_next(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "4")

        client.post(
            "/v2/work-order/routing-execution/start",
            json={"work_order_id": work_order_id, "seq_no": 20, "started_by": "operator-a"},
        )
        response = client.post(
            "/v2/work-order/routing-execution/release",
            json={"work_order_id": work_order_id, "seq_no": 20, "completed_by": "operator-b"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["active_state"]["has_active_step"])
        self.assertIsNone(payload["active_state"]["active_step"])

        steps = self._snapshot_steps(db, work_order_id)
        self.assertEqual([(row.seq_no, row.execution_status) for row in steps], [(10, "PENDING"), (20, "DONE"), (30, "PENDING")])

    def test_invalid_target_and_invalid_release_preserve_guard_behavior(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "5")

        invalid_start = client.post(
            "/v2/work-order/routing-execution/start",
            json={"work_order_id": work_order_id, "step_code": "QC", "started_by": "operator-a"},
        )
        self.assertEqual(invalid_start.status_code, 409)
        self.assertEqual(
            invalid_start.json()["detail"],
            "WorkOrder routing step target is not execution-eligible: step_code not found in snapshot_id=1: step_code=QC",
        )

        client.post(
            "/v2/work-order/routing-execution/start",
            json={"work_order_id": work_order_id, "seq_no": 20, "started_by": "operator-a"},
        )
        invalid_release = client.post(
            "/v2/work-order/routing-execution/release",
            json={"work_order_id": work_order_id, "seq_no": 30, "completed_by": "operator-b"},
        )

        self.assertEqual(invalid_release.status_code, 409)
        self.assertEqual(
            invalid_release.json()["detail"],
            "active step release target does not match current active step",
        )
        steps = self._snapshot_steps(db, work_order_id)
        self.assertEqual([(row.seq_no, row.execution_status) for row in steps], [(10, "PENDING"), (20, "ACTIVE"), (30, "PENDING")])

    def test_out_of_order_start_is_rejected_without_partial_write(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "5B")

        response = client.post(
            "/v2/work-order/routing-execution/start",
            json={"work_order_id": work_order_id, "seq_no": 30, "started_by": "operator-a"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["detail"],
            "WorkOrder routing step transition is not allowed: forward transition skips required snapshot step(s) in snapshot_id=1: skipped_seq_no=20",
        )

        steps = self._snapshot_steps(db, work_order_id)
        self.assertEqual([(row.seq_no, row.execution_status) for row in steps], [(10, "PENDING"), (20, "PENDING"), (30, "PENDING")])
        self.assertIsNone(steps[2].started_at)
        self.assertIsNone(steps[2].started_by)

    def test_failure_path_does_not_leave_half_written_state(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "6")

        original_commit = db.commit

        def broken_commit():
            raise RuntimeError("commit failed")

        db.commit = broken_commit
        try:
            response = client.post(
                "/v2/work-order/routing-execution/start",
                json={"work_order_id": work_order_id, "seq_no": 20, "started_by": "operator-a"},
            )
        finally:
            db.commit = original_commit

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.json()["detail"],
            f"WorkOrder routing step start failed and rolled back: work_order_id={work_order_id}",
        )

        rows = self._snapshot_steps(db, work_order_id)
        self.assertEqual([(row.seq_no, row.execution_status) for row in rows], [(10, "PENDING"), (20, "PENDING"), (30, "PENDING")])
        self.assertIsNone(rows[1].started_at)
        self.assertIsNone(rows[1].started_by)


if __name__ == "__main__":
    unittest.main()
