from __future__ import annotations

from datetime import date
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v2.shipment import router
from app.bootstrap.raw_material_uom_schema import ensure_raw_material_uom_columns
from app.bootstrap.work_order_fg_receive_schema import ensure_work_order_fg_receive_schema
from app.bootstrap.work_order_routing_execution_state_schema import ensure_work_order_routing_execution_state_columns
from app.bootstrap.work_order_shipment_schema import ensure_work_order_shipment_schema
from app.bootstrap.work_order_wip_transfer_schema import ensure_work_order_wip_transfer_schema
from app.schemas.work_order_fg_receive import WorkOrderFgReceiveCreateRequest
from app.schemas.work_order_wip_transfer import WorkOrderWipTransferCreateRequest, WorkOrderWipTransferQcDecisionRequest
from app.services.work_order_fg_receive import create_work_order_fg_receive
from app.services.work_order_mainline import create_work_order_record
from app.services.work_order_routing_step_active import guard_work_order_routing_snapshot_active_step
from app.services.work_order_routing_step_active_release import guard_work_order_routing_snapshot_active_step_release
from app.services.work_order_wip_transfer import apply_work_order_wip_transfer_qc_decision, create_work_order_wip_transfer
from database import Base, get_db
from models import Product, ProductionLine, RawMaterial, RoutingHeader, RoutingStep, SalesOrder, WorkOrderFgReceive
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
    ensure_work_order_shipment_schema(engine)
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


class WorkOrderShipmentTests(unittest.TestCase):
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
        sales_order = _add_sales_order(db, f"SO-SHP-{suffix}")
        product = _add_product(db, f"FG-SHP-{suffix}")
        line = _add_line(db, f"LINE-SHP-{suffix}")
        routing = _add_routing(db, f"FG-SHP-{suffix}")
        _add_step(db, routing.id, 10, "CUT", "Cutting", "Production", True)
        _add_step(db, routing.id, 20, "ASSY", "Assembly", "Production", True)
        _add_step(db, routing.id, 30, "PACK", "Packing", "Packing", True)
        db.commit()

        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no=f"WO-SHP-{suffix}",
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
        txn_qty: float = 5.0,
        txn_uom: str = "PCS",
    ) -> int:
        response = create_work_order_wip_transfer(
            db=db,
            work_order_id=work_order_id,
            payload=WorkOrderWipTransferCreateRequest(
                from_step_no=from_step_no,
                to_step_no=to_step_no,
                handling_unit_type="PALLET",
                handling_unit_label=f"WIP-{work_order_id}",
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

    def _create_fg_receive(
        self,
        db: Session,
        *,
        work_order_id: int,
        suffix: str,
        qty: float = 5.0,
        receive_status: str = "RECEIVED",
    ) -> int:
        _add_item_master(db, item_code=f"FG-SHP-{suffix}", unit="PCS")
        db.commit()
        self._mark_step_done(db, work_order_id, 10)
        self._mark_step_done(db, work_order_id, 20)
        transfer_id = self._create_transfer(db, work_order_id=work_order_id, from_step_no=20, to_step_no=30, txn_qty=qty)
        self._qc_pass(db, transfer_id)
        self._mark_step_done(db, work_order_id, 30)
        response = create_work_order_fg_receive(
            db=db,
            work_order_id=work_order_id,
            payload=WorkOrderFgReceiveCreateRequest(
                wip_transfer_id=transfer_id,
                fg_handling_unit_type="PALLET",
                fg_handling_unit_label=f"FG-{suffix}",
                txn_qty=qty,
                txn_uom="PCS",
                received_by="receiver-a",
                remark="baseline receipt",
            ),
        )
        if receive_status != "RECEIVED":
            row = db.query(WorkOrderFgReceive).filter(WorkOrderFgReceive.id == response.id).first()
            assert row is not None
            row.receive_status = receive_status
            db.add(row)
            db.commit()
        return response.id

    def test_received_fg_can_be_shipped_successfully(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "1")
        fg_receive_id = self._create_fg_receive(db, work_order_id=work_order_id, suffix="1")

        response = client.post(
            f"/work-orders/{work_order_id}/shipments",
            json={
                "fg_receive_id": fg_receive_id,
                "txn_qty": 5.0,
                "txn_uom": "PCS",
                "shipment_ref": "DO-001",
                "shipment_remark": "full ship",
                "shipped_by": "shipper-a",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["work_order_id"], work_order_id)
        self.assertEqual(payload["fg_receive_id"], fg_receive_id)
        self.assertEqual(payload["txn_qty"], 5.0)
        self.assertEqual(payload["txn_uom"], "PCS")
        self.assertEqual(payload["shipment_status"], "SHIPPED")
        self.assertEqual(payload["shipped_by"], "shipper-a")
        self.assertTrue(payload["shipment_no"].startswith(f"SHP-{work_order_id}-"))

    def test_non_received_fg_is_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "2")
        fg_receive_id = self._create_fg_receive(db, work_order_id=work_order_id, suffix="2", receive_status="PENDING")

        response = client.post(
            f"/work-orders/{work_order_id}/shipments",
            json={
                "fg_receive_id": fg_receive_id,
                "txn_qty": 1.0,
                "txn_uom": "PCS",
                "shipment_ref": "DO-002",
                "shipment_remark": "blocked",
                "shipped_by": "shipper-a",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("Shipment requires RECEIVED FG receive", response.json()["detail"])

    def test_shipment_qty_within_fg_qty_succeeds(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "3")
        fg_receive_id = self._create_fg_receive(db, work_order_id=work_order_id, suffix="3", qty=5.0)

        response = client.post(
            f"/work-orders/{work_order_id}/shipments",
            json={
                "fg_receive_id": fg_receive_id,
                "txn_qty": 3.0,
                "txn_uom": "PCS",
                "shipment_ref": "DO-003",
                "shipment_remark": "partial",
                "shipped_by": "shipper-a",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["txn_qty"], 3.0)

    def test_shipment_qty_exceeding_remaining_qty_is_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "4")
        fg_receive_id = self._create_fg_receive(db, work_order_id=work_order_id, suffix="4", qty=5.0)

        response = client.post(
            f"/work-orders/{work_order_id}/shipments",
            json={
                "fg_receive_id": fg_receive_id,
                "txn_qty": 6.0,
                "txn_uom": "PCS",
                "shipment_ref": "DO-004",
                "shipment_remark": "too much",
                "shipped_by": "shipper-a",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("Shipment qty exceeds remaining shippable qty", response.json()["detail"])

    def test_two_partial_shipments_within_total_fg_qty_succeed(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "5")
        fg_receive_id = self._create_fg_receive(db, work_order_id=work_order_id, suffix="5", qty=5.0)

        first = client.post(
            f"/work-orders/{work_order_id}/shipments",
            json={
                "fg_receive_id": fg_receive_id,
                "txn_qty": 2.0,
                "txn_uom": "PCS",
                "shipment_ref": "DO-005-A",
                "shipment_remark": "first partial",
                "shipped_by": "shipper-a",
            },
        )
        second = client.post(
            f"/work-orders/{work_order_id}/shipments",
            json={
                "fg_receive_id": fg_receive_id,
                "txn_qty": 3.0,
                "txn_uom": "PCS",
                "shipment_ref": "DO-005-B",
                "shipment_remark": "second partial",
                "shipped_by": "shipper-b",
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["shipment_status"], "SHIPPED")
        self.assertEqual(second.json()["shipment_status"], "SHIPPED")

    def test_later_over_shipment_attempt_is_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "6")
        fg_receive_id = self._create_fg_receive(db, work_order_id=work_order_id, suffix="6", qty=5.0)

        first = client.post(
            f"/work-orders/{work_order_id}/shipments",
            json={
                "fg_receive_id": fg_receive_id,
                "txn_qty": 4.0,
                "txn_uom": "PCS",
                "shipment_ref": "DO-006-A",
                "shipment_remark": "first partial",
                "shipped_by": "shipper-a",
            },
        )
        second = client.post(
            f"/work-orders/{work_order_id}/shipments",
            json={
                "fg_receive_id": fg_receive_id,
                "txn_qty": 2.0,
                "txn_uom": "PCS",
                "shipment_ref": "DO-006-B",
                "shipment_remark": "too much later",
                "shipped_by": "shipper-b",
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertIn("Shipment qty exceeds remaining shippable qty", second.json()["detail"])

    def test_get_list_returns_shipment_rows(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "7")
        fg_receive_id = self._create_fg_receive(db, work_order_id=work_order_id, suffix="7")
        create_response = client.post(
            f"/work-orders/{work_order_id}/shipments",
            json={
                "fg_receive_id": fg_receive_id,
                "txn_qty": 2.0,
                "txn_uom": "PCS",
                "shipment_ref": "DO-007",
                "shipment_remark": "list me",
                "shipped_by": "shipper-a",
            },
        )
        self.assertEqual(create_response.status_code, 200)

        listing = client.get(f"/work-orders/{work_order_id}/shipments")

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.json()), 1)
        self.assertEqual(listing.json()[0]["fg_receive_id"], fg_receive_id)
        self.assertEqual(listing.json()[0]["shipment_status"], "SHIPPED")

    def test_get_detail_returns_one_shipment_row_correctly(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "8")
        fg_receive_id = self._create_fg_receive(db, work_order_id=work_order_id, suffix="8")
        create_response = client.post(
            f"/work-orders/{work_order_id}/shipments",
            json={
                "fg_receive_id": fg_receive_id,
                "txn_qty": 1.0,
                "txn_uom": "PCS",
                "shipment_ref": "DO-008",
                "shipment_remark": "detail me",
                "shipped_by": "shipper-a",
            },
        )
        shipment_id = create_response.json()["id"]

        detail = client.get(f"/shipments/{shipment_id}")

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], shipment_id)
        self.assertEqual(detail.json()["shipment_ref"], "DO-008")
        self.assertEqual(detail.json()["shipment_status"], "SHIPPED")

    def test_shipment_does_not_modify_step_37_truth(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "9")
        fg_receive_id = self._create_fg_receive(db, work_order_id=work_order_id, suffix="9", qty=5.0)
        before = db.query(WorkOrderFgReceive).filter(WorkOrderFgReceive.id == fg_receive_id).first()
        assert before is not None
        before_snapshot = {
            "receive_status": before.receive_status,
            "txn_qty": before.txn_qty,
            "txn_uom": before.txn_uom,
            "received_by": before.received_by,
            "remark": before.remark,
            "wip_transfer_id": before.wip_transfer_id,
        }

        response = client.post(
            f"/work-orders/{work_order_id}/shipments",
            json={
                "fg_receive_id": fg_receive_id,
                "txn_qty": 2.0,
                "txn_uom": "PCS",
                "shipment_ref": "DO-009",
                "shipment_remark": "do not mutate receive",
                "shipped_by": "shipper-a",
            },
        )

        self.assertEqual(response.status_code, 200)
        after = db.query(WorkOrderFgReceive).filter(WorkOrderFgReceive.id == fg_receive_id).first()
        assert after is not None
        self.assertEqual(after.receive_status, before_snapshot["receive_status"])
        self.assertEqual(after.txn_qty, before_snapshot["txn_qty"])
        self.assertEqual(after.txn_uom, before_snapshot["txn_uom"])
        self.assertEqual(after.received_by, before_snapshot["received_by"])
        self.assertEqual(after.remark, before_snapshot["remark"])
        self.assertEqual(after.wip_transfer_id, before_snapshot["wip_transfer_id"])

    def test_shipment_status_is_shipped_only(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "10")
        fg_receive_id = self._create_fg_receive(db, work_order_id=work_order_id, suffix="10")

        response = client.post(
            f"/work-orders/{work_order_id}/shipments",
            json={
                "fg_receive_id": fg_receive_id,
                "txn_qty": 1.0,
                "txn_uom": "PCS",
                "shipment_ref": "DO-010",
                "shipment_remark": "status check",
                "shipped_by": "shipper-a",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["shipment_status"], "SHIPPED")
        detail = client.get(f"/shipments/{response.json()['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["shipment_status"], "SHIPPED")


if __name__ == "__main__":
    unittest.main()
