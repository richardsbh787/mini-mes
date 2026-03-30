from __future__ import annotations

from datetime import date, datetime, timedelta
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v2.fg_receive import router as fg_receive_router
from app.api.v2.step47_fg_receive import router as step47_fg_receive_router
from app.bootstrap.raw_material_uom_schema import ensure_raw_material_uom_columns
from app.bootstrap.stock_ledger_fg_receive_schema import ensure_stock_ledger_fg_receive_columns
from app.bootstrap.work_order_fg_receive_schema import ensure_work_order_fg_receive_schema
from app.bootstrap.work_order_routing_execution_state_schema import ensure_work_order_routing_execution_state_columns
from app.bootstrap.work_order_wip_transfer_schema import ensure_work_order_wip_transfer_schema
from app.schemas.work_order_wip_transfer import WorkOrderWipTransferCreateRequest, WorkOrderWipTransferQcDecisionRequest
from app.services.step47_fg_receive import get_fg_receive_step47_activation_state
from app.services.work_order_mainline import create_work_order_record
from app.services.work_order_routing_step_active import guard_work_order_routing_snapshot_active_step
from app.services.work_order_routing_step_active_release import guard_work_order_routing_snapshot_active_step_release
from app.services.work_order_wip_transfer import apply_work_order_wip_transfer_qc_decision, create_work_order_wip_transfer
from database import Base, get_db
from models import (
    FgReceiveEventTruth,
    FgReceiveLocationEvidenceSnapshot,
    FgReceiveLocationResolutionAttempt,
    LabelLocationMapping,
    LocationLabel,
    PhysicalLocation,
    Product,
    ProductionLine,
    RawMaterial,
    RoutingHeader,
    RoutingStep,
    SalesOrder,
    StockLedger,
    WorkOrderFgReceive,
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
    ensure_raw_material_uom_columns(engine)
    ensure_work_order_wip_transfer_schema(engine)
    ensure_work_order_fg_receive_schema(engine)
    ensure_stock_ledger_fg_receive_columns(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def _add_sales_order(db: Session, order_no: str) -> SalesOrder:
    row = SalesOrder(order_no=order_no, customer_name="Test Customer", order_date=date(2026, 3, 30), status="OPEN")
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


class Step47FgReceiveTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def _new_client(self, db: Session) -> TestClient:
        app = FastAPI()
        app.include_router(fg_receive_router)
        app.include_router(step47_fg_receive_router)

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
        model_no = product_model_no or f"FG-STEP47-{suffix}"
        sales_order = _add_sales_order(db, f"SO-STEP47-{suffix}")
        product = _add_product(db, model_no)
        line = _add_line(db, f"LINE-STEP47-{suffix}")
        routing = _add_routing(db, model_no)
        _add_step(db, routing.id, 10, "CUT", "Cutting", "Production", True)
        _add_step(db, routing.id, 20, "ASSY", "Assembly", "Production", True)
        _add_step(db, routing.id, 30, "PACK", "Packing", "Packing", True)
        db.commit()

        work_order = create_work_order_record(
            db=db,
            work_order=WorkOrderCreate(
                work_order_no=f"WO-STEP47-{suffix}",
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
        fg_handling_unit_label: str | None,
    ) -> int:
        work_order_id = self._create_work_order_with_snapshot(db, suffix, product_model_no=f"FG-STEP47-{suffix}")
        _add_item_master(db, item_code=f"FG-STEP47-{suffix}", unit="PCS")
        db.commit()
        self._mark_step_done(db, work_order_id, 10)
        self._mark_step_done(db, work_order_id, 20)
        transfer_id = self._create_transfer(
            db,
            work_order_id=work_order_id,
            from_step_no=20,
            to_step_no=30,
            handling_unit_label=f"WIP-{suffix}",
        )
        self._qc_pass(db, transfer_id)
        self._mark_step_done(db, work_order_id, 30)

        response = client.post(
            f"/work-orders/{work_order_id}/fg-receipts",
            json={
                "wip_transfer_id": transfer_id,
                "fg_handling_unit_type": "PALLET" if fg_handling_unit_label is not None else "LOOSE",
                "fg_handling_unit_label": fg_handling_unit_label,
                "txn_qty": 5.0,
                "txn_uom": "PCS",
                "received_by": "receiver-a",
                "remark": "step47 baseline",
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["id"]

    def _add_location_chain(
        self,
        db: Session,
        *,
        label_token: str,
        location_code: str,
        event_time: datetime,
        label_status: str = "ACTIVE",
        mapping_count: int = 1,
    ) -> None:
        location = PhysicalLocation(location_code=location_code, location_name=f"Location {location_code}", status="ACTIVE")
        db.add(location)
        db.flush()
        label = LocationLabel(label_token=label_token, label_type="PALLET_LABEL", status=label_status)
        db.add(label)
        db.flush()
        for offset in range(mapping_count):
            mapping = LabelLocationMapping(
                location_label_id=label.id,
                physical_location_id=location.id,
                status="ACTIVE",
                effective_from=event_time - timedelta(hours=1),
                effective_to=event_time + timedelta(hours=1 + offset),
            )
            db.add(mapping)
        db.commit()

    def test_success_path_creates_attempt_evidence_final_truth_and_ledger(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        fg_receive_id = self._create_fg_receive(db, client, suffix="1", fg_handling_unit_label="FG-LABEL-1")
        actual_fg_receive = db.query(WorkOrderFgReceive).filter_by(id=fg_receive_id).first()
        assert actual_fg_receive is not None
        self._add_location_chain(db, label_token="FG-LABEL-1", location_code="FG-LOC-1", event_time=actual_fg_receive.received_at)

        response = client.post(f"/v2/fg-receive-step47/{fg_receive_id}/execute", json={"executed_by": "store-a", "remark": "execute success"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["outcome_class"], "SUCCESS")
        self.assertFalse(payload["admitted_source_activation_active"])
        self.assertFalse(payload["runtime_production_use_authorized"])
        self.assertEqual(db.query(FgReceiveLocationResolutionAttempt).filter_by(fg_receive_id=fg_receive_id).count(), 1)
        self.assertEqual(db.query(FgReceiveLocationEvidenceSnapshot).filter_by(fg_receive_id=fg_receive_id).count(), 1)
        self.assertEqual(db.query(FgReceiveEventTruth).filter_by(fg_receive_id=fg_receive_id).count(), 1)
        truth = db.query(FgReceiveEventTruth).filter_by(fg_receive_id=fg_receive_id).first()
        assert truth is not None
        attempt = db.query(FgReceiveLocationResolutionAttempt).filter_by(fg_receive_id=fg_receive_id).first()
        evidence = db.query(FgReceiveLocationEvidenceSnapshot).filter_by(fg_receive_id=fg_receive_id).first()
        assert attempt is not None and evidence is not None
        self.assertEqual(truth.bound_from_resolution_attempt_id, attempt.id)
        self.assertEqual(truth.location_evidence_snapshot_ref, evidence.id)
        self.assertEqual(truth.bound_location_code, "FG-LOC-1")
        ledger_row = db.query(StockLedger).filter(StockLedger.source_event_id == fg_receive_id).first()
        assert ledger_row is not None
        self.assertEqual(ledger_row.location_id, "FG-LOC-1")
        self.assertEqual(ledger_row.stock_bucket, "FINISHED_GOODS")
        self.assertEqual(ledger_row.movement_type, "IN")

    def test_failed_ambiguous_and_unresolved_paths_create_no_final_truth(self) -> None:
        db = self._new_db()
        client = self._new_client(db)

        unresolved_id = self._create_fg_receive(db, client, suffix="2", fg_handling_unit_label=None)
        failed_id = self._create_fg_receive(db, client, suffix="3", fg_handling_unit_label="FG-LABEL-3")
        ambiguous_id = self._create_fg_receive(db, client, suffix="4", fg_handling_unit_label="FG-LABEL-4")

        failed_fg_receive = db.query(WorkOrderFgReceive).filter_by(id=failed_id).first()
        ambiguous_fg_receive = db.query(WorkOrderFgReceive).filter_by(id=ambiguous_id).first()
        assert failed_fg_receive is not None and ambiguous_fg_receive is not None
        label = LocationLabel(label_token="FG-LABEL-4", label_type="PALLET_LABEL", status="ACTIVE")
        location_a = PhysicalLocation(location_code="FG-LOC-4A", location_name="A", status="ACTIVE")
        location_b = PhysicalLocation(location_code="FG-LOC-4B", location_name="B", status="ACTIVE")
        db.add_all([label, location_a, location_b])
        db.flush()
        db.add_all(
            [
                LabelLocationMapping(
                    location_label_id=label.id,
                    physical_location_id=location_a.id,
                    status="ACTIVE",
                    effective_from=ambiguous_fg_receive.received_at - timedelta(hours=1),
                    effective_to=ambiguous_fg_receive.received_at + timedelta(hours=1),
                ),
                LabelLocationMapping(
                    location_label_id=label.id,
                    physical_location_id=location_b.id,
                    status="ACTIVE",
                    effective_from=ambiguous_fg_receive.received_at - timedelta(hours=1),
                    effective_to=ambiguous_fg_receive.received_at + timedelta(hours=2),
                ),
            ]
        )
        db.commit()

        unresolved = client.post(f"/v2/fg-receive-step47/{unresolved_id}/execute", json={"executed_by": "store-a"})
        failed = client.post(f"/v2/fg-receive-step47/{failed_id}/execute", json={"executed_by": "store-a"})
        ambiguous = client.post(f"/v2/fg-receive-step47/{ambiguous_id}/execute", json={"executed_by": "store-a"})

        self.assertEqual(unresolved.status_code, 200)
        self.assertEqual(failed.status_code, 200)
        self.assertEqual(ambiguous.status_code, 200)
        self.assertEqual(unresolved.json()["outcome_class"], "UNRESOLVED")
        self.assertEqual(failed.json()["outcome_class"], "FAILED")
        self.assertEqual(ambiguous.json()["outcome_class"], "AMBIGUOUS")
        self.assertEqual(db.query(FgReceiveEventTruth).filter(FgReceiveEventTruth.fg_receive_id.in_([unresolved_id, failed_id, ambiguous_id])).count(), 0)

    def test_one_final_binding_guard_holds(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        fg_receive_id = self._create_fg_receive(db, client, suffix="5", fg_handling_unit_label="FG-LABEL-5")
        fg_receive = db.query(WorkOrderFgReceive).filter_by(id=fg_receive_id).first()
        assert fg_receive is not None
        self._add_location_chain(db, label_token="FG-LABEL-5", location_code="FG-LOC-5", event_time=fg_receive.received_at)

        first = client.post(f"/v2/fg-receive-step47/{fg_receive_id}/execute", json={"executed_by": "store-a"})
        second = client.post(f"/v2/fg-receive-step47/{fg_receive_id}/execute", json={"executed_by": "store-b"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertIn("final truth already exists", second.json()["detail"])

    def test_live_master_changes_do_not_rewrite_old_event_truth(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        fg_receive_id = self._create_fg_receive(db, client, suffix="6", fg_handling_unit_label="FG-LABEL-6")
        fg_receive = db.query(WorkOrderFgReceive).filter_by(id=fg_receive_id).first()
        assert fg_receive is not None
        self._add_location_chain(db, label_token="FG-LABEL-6", location_code="FG-LOC-6", event_time=fg_receive.received_at)

        execute = client.post(f"/v2/fg-receive-step47/{fg_receive_id}/execute", json={"executed_by": "store-a"})
        self.assertEqual(execute.status_code, 200)

        evidence_before = db.query(FgReceiveLocationEvidenceSnapshot).filter_by(fg_receive_id=fg_receive_id).first()
        truth_before = db.query(FgReceiveEventTruth).filter_by(fg_receive_id=fg_receive_id).first()
        location = db.query(PhysicalLocation).filter_by(location_code="FG-LOC-6").first()
        assert evidence_before is not None and truth_before is not None and location is not None

        location.location_code = "FG-LOC-6-NEW"
        db.add(location)
        db.commit()

        evidence_after = db.query(FgReceiveLocationEvidenceSnapshot).filter_by(fg_receive_id=fg_receive_id).first()
        truth_after = db.query(FgReceiveEventTruth).filter_by(fg_receive_id=fg_receive_id).first()
        assert evidence_after is not None and truth_after is not None
        self.assertEqual(evidence_after.matched_location_code, "FG-LOC-6")
        self.assertEqual(truth_after.bound_location_code, "FG-LOC-6")

    def test_read_surfaces_do_not_mutate_state(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        fg_receive_id = self._create_fg_receive(db, client, suffix="7", fg_handling_unit_label="FG-LABEL-7")
        fg_receive = db.query(WorkOrderFgReceive).filter_by(id=fg_receive_id).first()
        assert fg_receive is not None
        self._add_location_chain(db, label_token="FG-LABEL-7", location_code="FG-LOC-7", event_time=fg_receive.received_at)
        execute = client.post(f"/v2/fg-receive-step47/{fg_receive_id}/execute", json={"executed_by": "store-a"})
        self.assertEqual(execute.status_code, 200)

        before = (
            db.query(FgReceiveLocationResolutionAttempt).count(),
            db.query(FgReceiveLocationEvidenceSnapshot).count(),
            db.query(FgReceiveEventTruth).count(),
            db.query(StockLedger).count(),
        )
        list_response = client.get("/v2/fg-receive-step47/list")
        detail_response = client.get(f"/v2/fg-receive-step47/{fg_receive_id}")
        summary_response = client.get("/v2/fg-receive-step47/summary")
        after = (
            db.query(FgReceiveLocationResolutionAttempt).count(),
            db.query(FgReceiveLocationEvidenceSnapshot).count(),
            db.query(FgReceiveEventTruth).count(),
            db.query(StockLedger).count(),
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(summary_response.status_code, 200)
        self.assertEqual(before, after)
        detail_payload = detail_response.json()
        self.assertEqual(detail_payload["source_event_context"]["fg_receive_id"], fg_receive_id)
        self.assertEqual(detail_payload["runtime_outcome"]["latest_outcome_class"], "SUCCESS")
        self.assertEqual(detail_payload["final_event_truth"]["bound_location_code"], "FG-LOC-7")

    def test_activation_remains_inactive_and_runtime_use_unauthorized(self) -> None:
        state = get_fg_receive_step47_activation_state()
        self.assertFalse(state["admitted_source_activation_active"])
        self.assertFalse(state["runtime_production_use_authorized"])

    def test_legal_position_write_depends_on_explicit_final_truth_not_convenience_inference(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        fg_receive_id = self._create_fg_receive(db, client, suffix="8", fg_handling_unit_label="FG-LABEL-8")
        fg_receive = db.query(WorkOrderFgReceive).filter_by(id=fg_receive_id).first()
        assert fg_receive is not None
        self._add_location_chain(db, label_token="FG-LABEL-8", location_code="FG-LOC-8", event_time=fg_receive.received_at, label_status="INACTIVE")

        response = client.post(f"/v2/fg-receive-step47/{fg_receive_id}/execute", json={"executed_by": "store-a"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["outcome_class"], "FAILED")
        self.assertEqual(db.query(FgReceiveEventTruth).filter_by(fg_receive_id=fg_receive_id).count(), 0)
        self.assertEqual(db.query(StockLedger).filter_by(source_event_id=fg_receive_id).count(), 0)


if __name__ == "__main__":
    unittest.main()
