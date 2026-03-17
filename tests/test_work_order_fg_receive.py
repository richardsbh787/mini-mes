from __future__ import annotations

from datetime import date
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v2.fg_receive import router
from app.bootstrap.raw_material_uom_schema import ensure_raw_material_uom_columns
from app.bootstrap.work_order_fg_receive_schema import ensure_work_order_fg_receive_schema
from app.bootstrap.work_order_routing_execution_state_schema import ensure_work_order_routing_execution_state_columns
from app.bootstrap.work_order_wip_transfer_schema import ensure_work_order_wip_transfer_schema
from app.schemas.work_order_wip_transfer import WorkOrderWipTransferCreateRequest, WorkOrderWipTransferQcDecisionRequest
from app.services.work_order_mainline import create_work_order_record
from app.services.work_order_routing_step_active import guard_work_order_routing_snapshot_active_step
from app.services.work_order_routing_step_active_release import guard_work_order_routing_snapshot_active_step_release
from app.services.work_order_wip_transfer import apply_work_order_wip_transfer_qc_decision, create_work_order_wip_transfer
from database import Base, get_db
from models import Product, ProductionLine, RawMaterial, RoutingHeader, RoutingStep, SalesOrder, WorkOrderWipTransfer
from schemas import WorkOrderCreate


def _make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    ensure_work_order_routing_execution_state_columns(engine)
    ensure_raw_material_uom_columns(engine)
    ensure_work_order_wip_transfer_schema(engine)
    ensure_work_order_fg_receive_schema(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def _add_sales_order(db: Session, order_no: str) -> SalesOrder:
    row = SalesOrder(order_no=order_no, customer_name="Test Customer", order_date=date(2026, 3, 16), status="OPEN")
    db.add(row)
    db.flush()
    return row


def _add_product(db: Session, model_no: str) -> Product:
    row = Product(model_no=model_no, model_description=f"Product {model_no}")
    db.add(row)
    db.flush()
    return row


def _add_line(db: Session, line_name: str) -> ProductionLine:
    row = ProductionLine(line_name=line_name, working_hours_per_day=8.0, efficiency_rate=1.0, is_active=True)
    db.add(row)
    db.flush()
    return row


def _add_routing(db: Session, item_code: str) -> RoutingHeader:
    row = RoutingHeader(item_code=item_code, routing_code=f"R-{item_code}", routing_name=f"Routing {item_code}", status="ACTIVE")
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


def _add_item_master(db: Session, *, item_code: str, unit: str) -> RawMaterial:
    row = RawMaterial(
        material_code=item_code,
        material_name=f"Item {item_code}",
        unit=unit,
        conversion_type="STANDARD",
        standard_conversion_ratio=1.0,
    )
    db.add(row)
    db.flush()
    return row


class WorkOrderFgReceiveTests(unittest.TestCase):
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

    def _create_work_order_with_snapshot(self, db: Session, suffix: str) -> int:
        sales_order = _add_sales_order(db, f"SO-FG-{suffix}")
        product = _add_product(db, f"FG-REC-{suffix}")
        line = _add_line(db, f"LINE-FG-{suffix}")
        routing = _add_routing(db, f"FG-REC-{suffix}")
        _add_step(db, routing.id, 10, "CUT", "Cutting", "Production", True)
        _add_step(db, routing.id, 20, "ASSY", "Assembly", "Production", True)
        _add_step(db, routing.id, 30, "PACK", "Packing", "Packing", True)
        db.commit()

        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no=f"WO-FG-{suffix}",
                sales_order_id=sales_order.id,
                product_id=product.id,
                production_line_id=line.id,
                routing_id=routing.id,
                planned_hours=4.0,
                priority="NORMAL",
                promise_date=date(2026, 4, 20),
                is_material_ready=True,
            ),
        )
        return work_order.id

    def _mark_step_done(self, db: Session, work_order_id: int, seq_no: int) -> None:
        guard_work_order_routing_snapshot_active_step(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=seq_no,
            target_seq_no=seq_no,
            active_seq_no=seq_no,
            started_by="operator-a",
        )
        guard_work_order_routing_snapshot_active_step_release(
            db=db,
            work_order_id=work_order_id,
            current_seq_no=seq_no,
            target_seq_no=seq_no,
            release_seq_no=seq_no,
            completed_by="operator-b",
        )

    def _create_transfer(
        self,
        db: Session,
        *,
        work_order_id: int,
        from_step_no: int,
        to_step_no: int,
        handling_unit_type: str = "PALLET",
        handling_unit_label: str | None = "WIP-001",
        txn_qty: float = 5.0,
        txn_uom: str = "PCS",
    ) -> int:
        response = create_work_order_wip_transfer(
            db=db,
            work_order_id=work_order_id,
            payload=WorkOrderWipTransferCreateRequest(
                from_step_no=from_step_no,
                to_step_no=to_step_no,
                handling_unit_type=handling_unit_type,
                handling_unit_label=handling_unit_label,
                txn_qty=txn_qty,
                txn_uom=txn_uom,
                created_by="operator-a",
            ),
        )
        return response.id

    def _qc_pass(self, db: Session, transfer_id: int) -> None:
        apply_work_order_wip_transfer_qc_decision(
            db=db,
            transfer_id=transfer_id,
            payload=WorkOrderWipTransferQcDecisionRequest(
                qc_decision="PASS",
                qc_decided_by="inspector-a",
                qc_remark="approved",
            ),
        )

    def _create_final_released_transfer(self, db: Session, suffix: str) -> tuple[int, int]:
        work_order_id = self._create_work_order_with_snapshot(db, suffix)
        _add_item_master(db, item_code=f"FG-REC-{suffix}", unit="PCS")
        db.commit()
        self._mark_step_done(db, work_order_id, 10)
        self._mark_step_done(db, work_order_id, 20)
        transfer_id = self._create_transfer(db, work_order_id=work_order_id, from_step_no=20, to_step_no=30, handling_unit_label=f"WIP-{suffix}")
        self._qc_pass(db, transfer_id)
        self._mark_step_done(db, work_order_id, 30)
        return work_order_id, transfer_id

    def test_released_final_transfer_can_be_fg_received_successfully(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id, transfer_id = self._create_final_released_transfer(db, "1")

        response = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "PALLET",
                "fg_handling_unit_label": "FG-001",
                "txn_qty": 5.0,
                "txn_uom": "PCS",
                "received_by": "receiver-a",
                "remark": "baseline receipt",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["work_order_id"], work_order_id)
        self.assertEqual(payload["wip_transfer_id"], transfer_id)
        self.assertEqual(payload["receive_status"], "RECEIVED")
        self.assertEqual(payload["fg_handling_unit_type"], "PALLET")
        self.assertEqual(payload["fg_handling_unit_label"], "FG-001")

    def test_non_released_transfer_is_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "2")
        _add_item_master(db, item_code="FG-REC-2", unit="PCS")
        db.commit()
        self._mark_step_done(db, work_order_id, 10)
        self._mark_step_done(db, work_order_id, 20)
        transfer_id = self._create_transfer(db, work_order_id=work_order_id, from_step_no=20, to_step_no=30, handling_unit_label="WIP-2")
        self._mark_step_done(db, work_order_id, 30)

        response = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "PALLET",
                "fg_handling_unit_label": "FG-002",
                "txn_qty": 5.0,
                "txn_uom": "PCS",
                "received_by": "receiver-a",
                "remark": "should fail",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("requires RELEASED WIP transfer", response.json()["detail"])

    def test_non_final_routing_output_transfer_is_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "3")
        _add_item_master(db, item_code="FG-REC-3", unit="PCS")
        db.commit()
        self._mark_step_done(db, work_order_id, 10)
        transfer_id = self._create_transfer(db, work_order_id=work_order_id, from_step_no=10, to_step_no=20, handling_unit_label="WIP-3")
        self._qc_pass(db, transfer_id)
        self._mark_step_done(db, work_order_id, 20)
        self._mark_step_done(db, work_order_id, 30)

        response = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "BIN",
                "fg_handling_unit_label": "FG-003",
                "txn_qty": 5.0,
                "txn_uom": "PCS",
                "received_by": "receiver-a",
                "remark": "should fail",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("final-routing-output transfer", response.json()["detail"])

    def test_invalid_qty_is_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id, transfer_id = self._create_final_released_transfer(db, "4")

        response = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "PALLET",
                "fg_handling_unit_label": "FG-004",
                "txn_qty": 0,
                "txn_uom": "PCS",
                "received_by": "receiver-a",
                "remark": "bad qty",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Invalid txn_qty for FG receive: txn_qty must be > 0")

    def test_invalid_fg_handling_unit_input_is_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id, transfer_id = self._create_final_released_transfer(db, "5")

        invalid_type = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "CRATE",
                "fg_handling_unit_label": "FG-005",
                "txn_qty": 5.0,
                "txn_uom": "PCS",
                "received_by": "receiver-a",
                "remark": "bad type",
            },
        )
        missing_label = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "PALLET",
                "fg_handling_unit_label": None,
                "txn_qty": 5.0,
                "txn_uom": "PCS",
                "received_by": "receiver-a",
                "remark": "missing label",
            },
        )

        self.assertEqual(invalid_type.status_code, 409)
        self.assertIn("Invalid fg_handling_unit_type", invalid_type.json()["detail"])
        self.assertEqual(missing_label.status_code, 409)
        self.assertIn("requires fg_handling_unit_label", missing_label.json()["detail"])

    def test_fg_receive_truth_is_persisted_correctly(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id, transfer_id = self._create_final_released_transfer(db, "6")

        create_response = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "LOOSE",
                "fg_handling_unit_label": None,
                "txn_qty": 3.0,
                "txn_uom": "PCS",
                "received_by": "receiver-b",
                "remark": "loose receipt",
            },
        )

        self.assertEqual(create_response.status_code, 200)
        fg_receive_id = create_response.json()["id"]
        detail = client.get(f"/fg-receipts/{fg_receive_id}")

        self.assertEqual(detail.status_code, 200)
        payload = detail.json()
        self.assertEqual(payload["work_order_id"], work_order_id)
        self.assertEqual(payload["wip_transfer_id"], transfer_id)
        self.assertEqual(payload["routing_snapshot_id"], create_response.json()["routing_snapshot_id"])
        self.assertEqual(payload["fg_handling_unit_type"], "LOOSE")
        self.assertIsNone(payload["fg_handling_unit_label"])
        self.assertEqual(payload["txn_qty"], 3.0)
        self.assertEqual(payload["txn_uom"], "PCS")
        self.assertEqual(payload["received_by"], "receiver-b")

    def test_duplicate_fg_receive_triggers_duplicate_guard(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id, transfer_id = self._create_final_released_transfer(db, "7")

        first = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "CARTON",
                "fg_handling_unit_label": "FG-007",
                "txn_qty": 5.0,
                "txn_uom": "PCS",
                "received_by": "receiver-a",
                "remark": "first",
            },
        )
        second = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "CARTON",
                "fg_handling_unit_label": "FG-007-B",
                "txn_qty": 5.0,
                "txn_uom": "PCS",
                "received_by": "receiver-a",
                "remark": "duplicate",
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertIn("Duplicate FG receive is not allowed", second.json()["detail"])

    def test_get_list_returns_fg_receipts(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id, transfer_id = self._create_final_released_transfer(db, "8")

        create_response = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "BIN",
                "fg_handling_unit_label": "FG-008",
                "txn_qty": 5.0,
                "txn_uom": "PCS",
                "received_by": "receiver-a",
                "remark": "list me",
            },
        )
        self.assertEqual(create_response.status_code, 200)

        listing = client.get(f"/work-orders/{work_order_id}/fg-receipts")

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.json()), 1)
        self.assertEqual(listing.json()[0]["wip_transfer_id"], transfer_id)

    def test_get_detail_returns_one_fg_receipt_correctly(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id, transfer_id = self._create_final_released_transfer(db, "9")

        create_response = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "PALLET",
                "fg_handling_unit_label": "FG-009",
                "txn_qty": 5.0,
                "txn_uom": "PCS",
                "received_by": "receiver-a",
                "remark": "detail me",
            },
        )
        fg_receive_id = create_response.json()["id"]

        detail = client.get(f"/fg-receipts/{fg_receive_id}")

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], fg_receive_id)
        self.assertEqual(detail.json()["fg_handling_unit_label"], "FG-009")

    def test_fg_receive_does_not_modify_transfer_status_or_qc_fields(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id, transfer_id = self._create_final_released_transfer(db, "10")
        before = db.query(WorkOrderWipTransfer).filter(WorkOrderWipTransfer.id == transfer_id).first()
        assert before is not None
        before_status = before.transfer_status
        before_qc_decision = before.qc_decision
        before_qc_decided_by = before.qc_decided_by
        before_qc_remark = before.qc_remark
        before_txn_qty = before.txn_qty

        response = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "PALLET",
                "fg_handling_unit_label": "FG-010",
                "txn_qty": 5.0,
                "txn_uom": "PCS",
                "received_by": "receiver-a",
                "remark": "do not mutate transfer",
            },
        )

        self.assertEqual(response.status_code, 200)
        after = db.query(WorkOrderWipTransfer).filter(WorkOrderWipTransfer.id == transfer_id).first()
        assert after is not None
        self.assertEqual(after.transfer_status, before_status)
        self.assertEqual(after.qc_decision, before_qc_decision)
        self.assertEqual(after.qc_decided_by, before_qc_decided_by)
        self.assertEqual(after.qc_remark, before_qc_remark)
        self.assertEqual(after.txn_qty, before_txn_qty)


if __name__ == "__main__":
    unittest.main()
