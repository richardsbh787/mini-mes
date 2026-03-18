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
from app.bootstrap.stock_ledger_fg_receive_schema import ensure_stock_ledger_fg_receive_columns
from app.bootstrap.work_order_fg_receive_schema import ensure_work_order_fg_receive_schema
from app.bootstrap.work_order_routing_execution_state_schema import ensure_work_order_routing_execution_state_columns
from app.bootstrap.work_order_wip_transfer_schema import ensure_work_order_wip_transfer_schema
from app.schemas.work_order_wip_transfer import WorkOrderWipTransferCreateRequest, WorkOrderWipTransferQcDecisionRequest
from app.services.work_order_mainline import create_work_order_record
from app.services.work_order_routing_step_active import guard_work_order_routing_snapshot_active_step
from app.services.work_order_routing_step_active_release import guard_work_order_routing_snapshot_active_step_release
from app.services.work_order_wip_transfer import apply_work_order_wip_transfer_qc_decision, create_work_order_wip_transfer
from database import Base, get_db
from models import Product, ProductionLine, RawMaterial, RoutingHeader, RoutingStep, SalesOrder, StockLedger, WorkOrderFgReceive
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
    ensure_stock_ledger_fg_receive_columns(engine)
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


class WorkOrderFgReceiveStockLedgerTests(unittest.TestCase):
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

    def _create_work_order_with_snapshot(self, db: Session, suffix: str, *, product_model_no: str | None = None) -> int:
        model_no = product_model_no or f"FG-LEDGER-{suffix}"
        sales_order = _add_sales_order(db, f"SO-LEDGER-{suffix}")
        product = _add_product(db, model_no)
        line = _add_line(db, f"LINE-LEDGER-{suffix}")
        routing = _add_routing(db, model_no)
        _add_step(db, routing.id, 10, "CUT", "Cutting", "Production", True)
        _add_step(db, routing.id, 20, "ASSY", "Assembly", "Production", True)
        _add_step(db, routing.id, 30, "PACK", "Packing", "Packing", True)
        db.commit()

        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no=f"WO-LEDGER-{suffix}",
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
        handling_unit_label: str,
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

    def _create_fg_receive(
        self,
        db: Session,
        client: TestClient,
        *,
        suffix: str,
        receive_status: str = "RECEIVED",
        item_code: str | None = None,
        txn_qty: float = 5.0,
        txn_uom: str = "PCS",
    ) -> int:
        resolved_item_code = item_code or f"FG-LEDGER-{suffix}"
        work_order_id = self._create_work_order_with_snapshot(db, suffix, product_model_no=resolved_item_code)
        _add_item_master(db, item_code=resolved_item_code, unit="PCS")
        db.commit()
        self._mark_step_done(db, work_order_id, 10)
        self._mark_step_done(db, work_order_id, 20)
        transfer_id = self._create_transfer(
            db,
            work_order_id=work_order_id,
            from_step_no=20,
            to_step_no=30,
            handling_unit_label=f"WIP-{suffix}",
            txn_qty=txn_qty,
            txn_uom=txn_uom,
        )
        self._qc_pass(db, transfer_id)
        self._mark_step_done(db, work_order_id, 30)

        response = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "PALLET",
                "fg_handling_unit_label": f"FG-{suffix}",
                "txn_qty": txn_qty,
                "txn_uom": txn_uom,
                "received_by": "receiver-a",
                "remark": "baseline receive",
            },
        )
        self.assertEqual(response.status_code, 200)
        fg_receive_id = response.json()["id"]

        if receive_status != "RECEIVED":
            row = db.query(WorkOrderFgReceive).filter(WorkOrderFgReceive.id == fg_receive_id).first()
            assert row is not None
            row.receive_status = receive_status
            db.add(row)
            db.commit()

        return fg_receive_id

    def test_received_fg_receive_can_post_stock_ledger_successfully(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "1", product_model_no="FG-LEDGER-1")
        _add_item_master(db, item_code="FG-LEDGER-1", unit="PCS")
        db.commit()
        self._mark_step_done(db, work_order_id, 10)
        self._mark_step_done(db, work_order_id, 20)
        transfer_id = self._create_transfer(db, work_order_id=work_order_id, from_step_no=20, to_step_no=30, handling_unit_label="WIP-1")
        self._qc_pass(db, transfer_id)
        self._mark_step_done(db, work_order_id, 30)

        receive_response = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "PALLET",
                "fg_handling_unit_label": "FG-1",
                "txn_qty": 5.0,
                "txn_uom": "PCS",
                "received_by": "receiver-a",
                "remark": "receipt complete",
            },
        )
        fg_receive_id = receive_response.json()["id"]

        response = client.post(
            f"/fg-receipts/{fg_receive_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "post inbound"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source_event_type"], "FG_RECEIVE")
        self.assertEqual(payload["source_event_id"], fg_receive_id)
        self.assertEqual(payload["work_order_id"], work_order_id)
        self.assertEqual(payload["item_code"], "FG-LEDGER-1")
        self.assertEqual(payload["movement_type"], "IN")
        self.assertEqual(payload["stock_bucket"], "FINISHED_GOODS")
        self.assertEqual((payload["txn_qty"], payload["txn_uom"], payload["base_qty"], payload["base_uom"]), (5.0, "PCS", 5.0, "PCS"))
        self.assertEqual(payload["posted_by"], "store-a")
        self.assertEqual(payload["remark"], "post inbound")
        self.assertTrue(payload["ledger_no"].startswith("SLED-"))

        row = db.query(StockLedger).filter(StockLedger.source_event_id == fg_receive_id).first()
        assert row is not None
        self.assertEqual(row.item_code, "FG-LEDGER-1")
        self.assertEqual(row.item_id, "FG-LEDGER-1")
        self.assertEqual(row.txn_type, "RECEIPT")
        self.assertEqual(row.movement_type, "IN")
        self.assertEqual(row.stock_bucket, "FINISHED_GOODS")
        self.assertEqual((row.txn_qty, row.txn_uom, row.base_qty, row.base_uom), (5.0, "PCS", 5.0, "PCS"))

    def test_non_received_fg_receive_is_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        fg_receive_id = self._create_fg_receive(db, client, suffix="2", receive_status="PENDING")

        response = client.post(
            f"/fg-receipts/{fg_receive_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "should fail"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("requires RECEIVED status", response.json()["detail"])

    def test_duplicate_posting_for_same_fg_receive_is_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        fg_receive_id = self._create_fg_receive(db, client, suffix="3")

        first = client.post(
            f"/fg-receipts/{fg_receive_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "first"},
        )
        second = client.post(
            f"/fg-receipts/{fg_receive_id}/post-ledger",
            json={"posted_by": "store-b", "remark": "second"},
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertIn("Duplicate FG receive stock ledger posting is not allowed", second.json()["detail"])

    def test_duplicate_guard_runs_before_item_resolution(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        fg_receive_id = self._create_fg_receive(db, client, suffix="4")

        first = client.post(
            f"/fg-receipts/{fg_receive_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "first"},
        )
        self.assertEqual(first.status_code, 200)

        item_row = db.query(RawMaterial).filter(RawMaterial.material_code == "FG-LEDGER-4").first()
        assert item_row is not None
        db.delete(item_row)
        db.commit()

        second = client.post(
            f"/fg-receipts/{fg_receive_id}/post-ledger",
            json={"posted_by": "store-b", "remark": "duplicate should fail fast"},
        )

        self.assertEqual(second.status_code, 409)
        self.assertIn("Duplicate FG receive stock ledger posting is not allowed", second.json()["detail"])

    def test_item_resolution_follows_product_model_no_to_material_code_path(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        fg_receive_id = self._create_fg_receive(db, client, suffix="5", item_code="FG-PATH-5")

        response = client.post(
            f"/fg-receipts/{fg_receive_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "path check"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["item_code"], "FG-PATH-5")

    def test_base_resolution_uses_sf01_conversion_rules(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "6", product_model_no="FG-CONV-6")
        _add_item_master(db, item_code="FG-CONV-6", unit="PCS", standard_conversion_ratio=12.0)
        db.commit()
        self._mark_step_done(db, work_order_id, 10)
        self._mark_step_done(db, work_order_id, 20)
        transfer_id = self._create_transfer(
            db,
            work_order_id=work_order_id,
            from_step_no=20,
            to_step_no=30,
            handling_unit_label="WIP-6",
            txn_qty=2.0,
            txn_uom="BOX",
        )
        self._qc_pass(db, transfer_id)
        self._mark_step_done(db, work_order_id, 30)

        receive_response = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "PALLET",
                "fg_handling_unit_label": "FG-6",
                "txn_qty": 2.0,
                "txn_uom": "BOX",
                "received_by": "receiver-a",
                "remark": "conversion receive",
            },
        )
        fg_receive_id = receive_response.json()["id"]

        response = client.post(
            f"/fg-receipts/{fg_receive_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "sf01 conversion"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json()["txn_qty"], response.json()["txn_uom"]), (2.0, "BOX"))
        self.assertEqual((response.json()["base_qty"], response.json()["base_uom"]), (24.0, "PCS"))

    def test_missing_item_resolution_is_rejected_with_clear_detail(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order_id = self._create_work_order_with_snapshot(db, "7", product_model_no="FG-MISSING-7")
        db.commit()
        self._mark_step_done(db, work_order_id, 10)
        self._mark_step_done(db, work_order_id, 20)
        transfer_id = self._create_transfer(db, work_order_id=work_order_id, from_step_no=20, to_step_no=30, handling_unit_label="WIP-7")
        self._qc_pass(db, transfer_id)
        self._mark_step_done(db, work_order_id, 30)

        receive_response = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "PALLET",
                "fg_handling_unit_label": "FG-7",
                "txn_qty": 5.0,
                "txn_uom": "PCS",
                "received_by": "receiver-a",
                "remark": "missing item",
            },
        )
        fg_receive_id = receive_response.json()["id"]

        response = client.post(
            f"/fg-receipts/{fg_receive_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "should fail"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("work_order -> product.model_no -> RawMaterial.material_code", response.json()["detail"])
        self.assertIn("product_model_no=FG-MISSING-7", response.json()["detail"])

    def test_step_39a_does_not_modify_step_37_truth(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        fg_receive_id = self._create_fg_receive(db, client, suffix="8")

        before = db.query(WorkOrderFgReceive).filter(WorkOrderFgReceive.id == fg_receive_id).first()
        assert before is not None
        before_snapshot = (
            before.receive_status,
            before.received_at,
            before.received_by,
            before.txn_qty,
            before.txn_uom,
            before.remark,
        )

        response = client.post(
            f"/fg-receipts/{fg_receive_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "no mutate"},
        )

        self.assertEqual(response.status_code, 200)
        after = db.query(WorkOrderFgReceive).filter(WorkOrderFgReceive.id == fg_receive_id).first()
        assert after is not None
        after_snapshot = (
            after.receive_status,
            after.received_at,
            after.received_by,
            after.txn_qty,
            after.txn_uom,
            after.remark,
        )
        self.assertEqual(after_snapshot, before_snapshot)

    def test_read_surface_returns_posted_ledger_row_correctly(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        fg_receive_id = self._create_fg_receive(db, client, suffix="9")

        post_response = client.post(
            f"/fg-receipts/{fg_receive_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "read me"},
        )
        self.assertEqual(post_response.status_code, 200)

        detail = client.get(f"/stock-ledger/fg-receipts/{fg_receive_id}")

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json(), post_response.json())


if __name__ == "__main__":
    unittest.main()
