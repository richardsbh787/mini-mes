from __future__ import annotations

from datetime import date
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v2.work_order_wip_transfer import router
from app.bootstrap.raw_material_uom_schema import ensure_raw_material_uom_columns
from app.bootstrap.work_order_routing_execution_state_schema import ensure_work_order_routing_execution_state_columns
from app.bootstrap.work_order_wip_transfer_schema import ensure_work_order_wip_transfer_schema
from app.services.work_order_mainline import create_work_order_record
from app.services.work_order_routing_step_active import guard_work_order_routing_snapshot_active_step
from app.services.work_order_routing_step_active_release import guard_work_order_routing_snapshot_active_step_release
from database import Base, get_db
from models import Product, ProductionLine, RawMaterial, RoutingHeader, RoutingStep, SalesOrder
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


def _add_item_master(
    db: Session,
    *,
    item_code: str,
    unit: str,
    conversion_type: str = "STANDARD",
    standard_conversion_ratio: float = 1.0,
) -> RawMaterial:
    row = RawMaterial(
        material_code=item_code,
        material_name=f"Item {item_code}",
        unit=unit,
        conversion_type=conversion_type,
        standard_conversion_ratio=standard_conversion_ratio,
    )
    db.add(row)
    db.flush()
    return row


class WorkOrderWipTransferTests(unittest.TestCase):
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
        sales_order = _add_sales_order(db, f"SO-WIP-{suffix}")
        product = _add_product(db, f"FG-WIP-{suffix}")
        line = _add_line(db, f"LINE-WIP-{suffix}")
        routing = _add_routing(db, f"FG-WIP-{suffix}")
        _add_step(db, routing.id, 10, "CUT", "Cutting", "Production", True)
        _add_step(db, routing.id, 20, "ASSY", "Assembly", "Production", True)
        _add_step(db, routing.id, 30, "PACK", "Packing", "Packing", False)
        db.commit()

        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no=f"WO-WIP-{suffix}",
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
        client: TestClient,
        work_order_id: int,
        *,
        handling_unit_type: str = "PALLET",
        handling_unit_label: str | None = "P-001",
        txn_qty: float = 5.0,
        txn_uom: str = "PCS",
    ):
        return client.post(
            f"/work-orders/{work_order_id}/wip-transfers",
            json={
                "from_step_no": 10,
                "to_step_no": 20,
                "handling_unit_type": handling_unit_type,
                "handling_unit_label": handling_unit_label,
                "txn_qty": txn_qty,
                "txn_uom": txn_uom,
                "created_by": "operator-a",
            },
        )

    def _qc_decide(self, client: TestClient, transfer_id: int, qc_decision: str, qc_remark: str = "checked"):
        return client.post(
            f"/wip-transfers/{transfer_id}/qc-decision",
            json={
                "qc_decision": qc_decision,
                "qc_decided_by": "inspector-a",
                "qc_remark": qc_remark,
            },
        )

    def test_transfer_can_be_created_when_from_step_is_done(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "1")
        _add_item_master(db, item_code="FG-WIP-1", unit="PCS")
        db.commit()
        self._mark_step_done(db, work_order_id, 10)

        response = self._create_transfer(client, work_order_id)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["work_order_id"], work_order_id)
        self.assertEqual(payload["transfer_status"], "CREATED")
        self.assertEqual(payload["txn_qty"], 5.0)
        self.assertEqual(payload["txn_uom"], "PCS")
        self.assertEqual(payload["base_qty"], 5.0)
        self.assertEqual(payload["base_uom"], "PCS")

    def test_transfer_rejected_when_from_step_not_done(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "2")

        response = self._create_transfer(client, work_order_id, handling_unit_label="P-002")

        self.assertEqual(response.status_code, 409)
        self.assertIn("WIP transfer source step is not DONE", response.json()["detail"])

    def test_illegal_routing_path_is_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "3")
        self._mark_step_done(db, work_order_id, 10)

        response = client.post(
            f"/work-orders/{work_order_id}/wip-transfers",
            json={
                "from_step_no": 10,
                "to_step_no": 30,
                "handling_unit_type": "PALLET",
                "handling_unit_label": "P-003",
                "txn_qty": 5.0,
                "txn_uom": "PCS",
                "created_by": "operator-a",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("WIP transfer route linkage is invalid", response.json()["detail"])

    def test_illegal_qty_is_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "4")
        self._mark_step_done(db, work_order_id, 10)

        response = client.post(
            f"/work-orders/{work_order_id}/wip-transfers",
            json={
                "from_step_no": 10,
                "to_step_no": 20,
                "handling_unit_type": "PALLET",
                "handling_unit_label": "P-004",
                "txn_qty": 0,
                "txn_uom": "PCS",
                "created_by": "operator-a",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Invalid txn_qty for WIP transfer: txn_qty must be > 0")

    def test_illegal_handling_unit_input_is_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "5")
        self._mark_step_done(db, work_order_id, 10)

        invalid_type = client.post(
            f"/work-orders/{work_order_id}/wip-transfers",
            json={
                "from_step_no": 10,
                "to_step_no": 20,
                "handling_unit_type": "CRATE",
                "handling_unit_label": "H-1",
                "txn_qty": 1.0,
                "txn_uom": "PCS",
                "created_by": "operator-a",
            },
        )
        missing_label = client.post(
            f"/work-orders/{work_order_id}/wip-transfers",
            json={
                "from_step_no": 10,
                "to_step_no": 20,
                "handling_unit_type": "PALLET",
                "handling_unit_label": None,
                "txn_qty": 1.0,
                "txn_uom": "PCS",
                "created_by": "operator-a",
            },
        )

        self.assertEqual(invalid_type.status_code, 409)
        self.assertIn("Invalid handling_unit_type", invalid_type.json()["detail"])
        self.assertEqual(missing_label.status_code, 409)
        self.assertIn("requires handling_unit_label", missing_label.json()["detail"])

    def test_dual_quantity_fields_are_persisted_with_conversion(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "6")
        _add_item_master(db, item_code="FG-WIP-6", unit="PCS", conversion_type="STANDARD", standard_conversion_ratio=12.0)
        db.commit()
        self._mark_step_done(db, work_order_id, 10)

        response = client.post(
            f"/work-orders/{work_order_id}/wip-transfers",
            json={
                "from_step_no": 10,
                "to_step_no": 20,
                "handling_unit_type": "ROLL",
                "handling_unit_label": "R-006",
                "txn_qty": 2.0,
                "txn_uom": "BOX",
                "created_by": "operator-a",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual((payload["txn_qty"], payload["txn_uom"], payload["base_qty"], payload["base_uom"]), (2.0, "BOX", 24.0, "PCS"))

    def test_missing_sf01_conversion_rule_rejects_when_conversion_needed(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "7")
        _add_item_master(db, item_code="FG-WIP-7", unit="PCS", conversion_type="LOT_ACTUAL", standard_conversion_ratio=1.0)
        db.commit()
        self._mark_step_done(db, work_order_id, 10)

        response = client.post(
            f"/work-orders/{work_order_id}/wip-transfers",
            json={
                "from_step_no": 10,
                "to_step_no": 20,
                "handling_unit_type": "BIN",
                "handling_unit_label": "B-007",
                "txn_qty": 3.0,
                "txn_uom": "BOX",
                "created_by": "operator-a",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("WIP transfer conversion could not be resolved through SF-01", response.json()["detail"])

    def test_get_list_returns_transfer_records(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "8")
        self._mark_step_done(db, work_order_id, 10)

        create_response = self._create_transfer(
            client,
            work_order_id,
            handling_unit_type="LOOSE",
            handling_unit_label=None,
            txn_qty=1.0,
        )
        self.assertEqual(create_response.status_code, 200)

        list_response = client.get(f"/work-orders/{work_order_id}/wip-transfers")

        self.assertEqual(list_response.status_code, 200)
        payload = list_response.json()
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["transfer_status"], "CREATED")

    def test_get_detail_returns_single_transfer_detail(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "9")
        self._mark_step_done(db, work_order_id, 10)

        create_response = self._create_transfer(
            client,
            work_order_id,
            handling_unit_type="TRAY",
            handling_unit_label="T-009",
            txn_qty=4.0,
        )
        transfer_id = create_response.json()["id"]

        detail_response = client.get(f"/wip-transfers/{transfer_id}")

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.json()["id"], transfer_id)
        self.assertEqual(detail_response.json()["handling_unit_type"], "TRAY")

    def test_duplicate_request_triggers_duplicate_guard(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "10")
        self._mark_step_done(db, work_order_id, 10)

        first = self._create_transfer(
            client,
            work_order_id,
            handling_unit_type="CARTON",
            handling_unit_label="C-010",
            txn_qty=2.0,
        )
        second = self._create_transfer(
            client,
            work_order_id,
            handling_unit_type="CARTON",
            handling_unit_label="C-010",
            txn_qty=2.0,
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertIn("Duplicate WIP transfer is not allowed", second.json()["detail"])

    def test_created_transfer_accepts_pass(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "11")
        self._mark_step_done(db, work_order_id, 10)
        transfer_id = self._create_transfer(client, work_order_id, handling_unit_label="P-011").json()["id"]

        response = self._qc_decide(client, transfer_id, "PASS", "ok")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["qc_decision"], "PASS")

    def test_created_transfer_accepts_hold(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "12")
        self._mark_step_done(db, work_order_id, 10)
        transfer_id = self._create_transfer(client, work_order_id, handling_unit_label="P-012").json()["id"]

        response = self._qc_decide(client, transfer_id, "HOLD", "hold")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["qc_decision"], "HOLD")

    def test_created_transfer_accepts_rework(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "13")
        self._mark_step_done(db, work_order_id, 10)
        transfer_id = self._create_transfer(client, work_order_id, handling_unit_label="P-013").json()["id"]

        response = self._qc_decide(client, transfer_id, "REWORK", "redo")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["qc_decision"], "REWORK")

    def test_pass_results_in_released_status_and_true_availability(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "14")
        self._mark_step_done(db, work_order_id, 10)
        transfer_id = self._create_transfer(client, work_order_id, handling_unit_label="P-014").json()["id"]

        response = self._qc_decide(client, transfer_id, "PASS", "ok")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["transfer_status"], "RELEASED")
        self.assertTrue(payload["is_available_for_next_step"])

    def test_hold_results_in_qc_locked_status_and_false_availability(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "15")
        self._mark_step_done(db, work_order_id, 10)
        transfer_id = self._create_transfer(client, work_order_id, handling_unit_label="P-015").json()["id"]

        response = self._qc_decide(client, transfer_id, "HOLD", "hold")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["transfer_status"], "QC_LOCKED")
        self.assertFalse(payload["is_available_for_next_step"])

    def test_rework_results_in_qc_locked_status_and_false_availability(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "16")
        self._mark_step_done(db, work_order_id, 10)
        transfer_id = self._create_transfer(client, work_order_id, handling_unit_label="P-016").json()["id"]

        response = self._qc_decide(client, transfer_id, "REWORK", "redo")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["transfer_status"], "QC_LOCKED")
        self.assertFalse(payload["is_available_for_next_step"])

    def test_repeated_qc_decision_is_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "17")
        self._mark_step_done(db, work_order_id, 10)
        transfer_id = self._create_transfer(client, work_order_id, handling_unit_label="P-017").json()["id"]
        first = self._qc_decide(client, transfer_id, "PASS", "ok")
        second = self._qc_decide(client, transfer_id, "PASS", "again")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertIn("not allowed for current transfer_status", second.json()["detail"])

    def test_invalid_qc_decision_is_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "18")
        self._mark_step_done(db, work_order_id, 10)
        transfer_id = self._create_transfer(client, work_order_id, handling_unit_label="P-018").json()["id"]

        response = self._qc_decide(client, transfer_id, "SCRAP", "bad")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Invalid qc_decision for WIP transfer: qc_decision=SCRAP")

    def test_missing_transfer_is_rejected_for_qc(self) -> None:
        db = self._new_db()
        client = self._new_client(db)

        response = self._qc_decide(client, 999, "PASS", "ok")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "WIP transfer not found: id=999")

    def test_get_detail_and_list_expose_qc_fields_and_derived_availability(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "19")
        self._mark_step_done(db, work_order_id, 10)
        transfer_id = self._create_transfer(client, work_order_id, handling_unit_label="P-019").json()["id"]
        self._qc_decide(client, transfer_id, "PASS", "approved")

        detail = client.get(f"/wip-transfers/{transfer_id}")
        listing = client.get(f"/work-orders/{work_order_id}/wip-transfers")

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["qc_decision"], "PASS")
        self.assertEqual(detail.json()["qc_decided_by"], "inspector-a")
        self.assertEqual(detail.json()["qc_remark"], "approved")
        self.assertTrue(detail.json()["is_available_for_next_step"])

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()[0]["qc_decision"], "PASS")
        self.assertTrue(listing.json()[0]["is_available_for_next_step"])


if __name__ == "__main__":
    unittest.main()
