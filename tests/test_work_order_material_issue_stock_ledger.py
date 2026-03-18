from __future__ import annotations

from datetime import date
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v2.material_issue_stock_ledger import router
from app.api.v2.work_order_material_issue_commit import work_order_material_issue_commit
from app.bootstrap.material_issue_trace_schema import ensure_material_issue_trace_schema
from app.bootstrap.raw_material_uom_schema import ensure_raw_material_uom_columns
from app.bootstrap.stock_ledger_fg_receive_schema import ensure_stock_ledger_fg_receive_columns
from app.schemas.work_order_material_issue_commit import WorkOrderMaterialIssueCommitRequest
from database import Base, get_db
from models import (
    MaterialIssueEvent,
    Product,
    ProductionLine,
    RawMaterial,
    SalesOrder,
    StockLedger,
    WorkOrder,
    WorkOrderBOMSnapshot,
    WorkOrderBOMSnapshotLine,
)


def _make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    ensure_material_issue_trace_schema(engine)
    ensure_raw_material_uom_columns(engine)
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


def _add_work_order(db: Session, suffix: str) -> WorkOrder:
    sales_order = _add_sales_order(db, f"SO-RMI-{suffix}")
    product = _add_product(db, f"FG-RMI-{suffix}")
    line = _add_line(db, f"LINE-RMI-{suffix}")
    row = WorkOrder(
        work_order_no=f"WO-RMI-{suffix}",
        sales_order_id=sales_order.id,
        product_id=product.id,
        production_line_id=line.id,
        routing_id=None,
        planned_hours=4.0,
        actual_hours=0.0,
        remaining_hours=4.0,
        priority="NORMAL",
        promise_date=date(2026, 4, 20),
        is_material_ready=True,
        status="OPEN",
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


class WorkOrderMaterialIssueStockLedgerTests(unittest.TestCase):
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

    def _create_snapshot(
        self,
        db: Session,
        *,
        suffix: str,
        line_defs: list[dict],
        status: str = "RELEASED",
        issue_status: str = "PENDING",
    ) -> WorkOrderBOMSnapshot:
        work_order = _add_work_order(db, suffix)
        snapshot = WorkOrderBOMSnapshot(
            work_order_no=work_order.work_order_no,
            parent_system_item_code=f"FG-RMI-{suffix}",
            work_order_qty=2.0,
            bom_version_id=101,
            status=status,
            issue_status=issue_status,
            created_by="planner",
        )
        db.add(snapshot)
        db.flush()

        for index, line_def in enumerate(line_defs, start=1):
            db.add(
                WorkOrderBOMSnapshotLine(
                    snapshot_id=snapshot.id,
                    seq_no=index,
                    item_code=line_def["item_code"],
                    item_name=line_def.get("item_name"),
                    required_qty=line_def["required_qty"],
                    uom=line_def["uom"],
                )
            )

        db.commit()
        db.refresh(snapshot)
        return snapshot

    def _commit_issue_event(
        self,
        db: Session,
        *,
        snapshot_id: int,
        org_id: str = "ORG-1",
        location_id: str = "RM-STORE",
        issued_by: str = "store-a",
    ) -> int:
        result = work_order_material_issue_commit(
            payload=WorkOrderMaterialIssueCommitRequest(
                snapshot_id=snapshot_id,
                org_id=org_id,
                location_id=location_id,
                issued_by=issued_by,
            ),
            db=db,
        )
        self.assertEqual(result["issue_status"], "ISSUED")
        issue_event = db.query(MaterialIssueEvent).filter(MaterialIssueEvent.snapshot_id == snapshot_id).first()
        assert issue_event is not None
        return issue_event.issue_event_id

    def _create_manual_issue_event(
        self,
        db: Session,
        *,
        snapshot: WorkOrderBOMSnapshot,
        org_id: str = "ORG-1",
        location_id: str = "RM-STORE",
        issued_by: str = "store-a",
    ) -> int:
        row = MaterialIssueEvent(
            snapshot_id=snapshot.id,
            work_order_no=snapshot.work_order_no,
            bom_version_id=snapshot.bom_version_id,
            org_id=org_id,
            location_id=location_id,
            issued_by=issued_by,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.issue_event_id

    def test_committed_rm_issue_can_post_ledger_successfully(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        snapshot = self._create_snapshot(
            db,
            suffix="1",
            line_defs=[
                {"item_code": "RM-1A", "required_qty": 2.0, "uom": "PCS"},
                {"item_code": "RM-1B", "required_qty": 5.0, "uom": "KG"},
            ],
        )
        _add_item_master(db, item_code="RM-1A", unit="PCS")
        _add_item_master(db, item_code="RM-1B", unit="KG")
        db.commit()
        issue_event_id = self._commit_issue_event(db, snapshot_id=snapshot.id)

        response = client.post(
            f"/rm-issues/{issue_event_id}/post-ledger",
            json={"posted_by": "store-b", "remark": "post raw issue"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload), 2)
        self.assertEqual([row["item_code"] for row in payload], ["RM-1A", "RM-1B"])
        self.assertTrue(all(row["source_event_type"] == "RM_ISSUE" for row in payload))
        self.assertTrue(all(row["source_event_id"] == issue_event_id for row in payload))
        self.assertTrue(all(row["movement_type"] == "OUT" for row in payload))
        self.assertTrue(all(row["stock_bucket"] == "RAW_MATERIAL" for row in payload))
        self.assertEqual([(row["txn_qty"], row["txn_uom"], row["base_qty"], row["base_uom"]) for row in payload], [(2.0, "PCS", 2.0, "PCS"), (5.0, "KG", 5.0, "KG")])
        self.assertTrue(all(row["ledger_no"].startswith("SLED-") for row in payload))

        rows = (
            db.query(StockLedger)
            .filter(StockLedger.source_event_id == issue_event_id)
            .order_by(StockLedger.source_event_line_id.asc())
            .all()
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual([(row.item_code, row.qty, row.txn_type) for row in rows], [("RM-1A", -2.0, "ISSUE"), ("RM-1B", -5.0, "ISSUE")])

    def test_non_success_rm_issue_is_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        snapshot = self._create_snapshot(
            db,
            suffix="2",
            line_defs=[{"item_code": "RM-2A", "required_qty": 2.0, "uom": "PCS"}],
            issue_status="PENDING",
        )
        _add_item_master(db, item_code="RM-2A", unit="PCS")
        db.commit()
        issue_event_id = self._create_manual_issue_event(db, snapshot=snapshot)

        response = client.post(
            f"/rm-issues/{issue_event_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "should fail"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("requires committed issue truth", response.json()["detail"])

    def test_missing_issue_lines_is_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        snapshot = self._create_snapshot(db, suffix="3", line_defs=[], issue_status="ISSUED")
        issue_event_id = self._create_manual_issue_event(db, snapshot=snapshot)

        response = client.post(
            f"/rm-issues/{issue_event_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "no lines"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("has no persisted issue lines", response.json()["detail"])

    def test_duplicate_posting_is_checked_per_line_not_only_per_event(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        snapshot = self._create_snapshot(
            db,
            suffix="4",
            line_defs=[
                {"item_code": "RM-4A", "required_qty": 2.0, "uom": "PCS"},
                {"item_code": "RM-4B", "required_qty": 3.0, "uom": "PCS"},
            ],
            issue_status="ISSUED",
        )
        _add_item_master(db, item_code="RM-4A", unit="PCS")
        _add_item_master(db, item_code="RM-4B", unit="PCS")
        db.commit()
        issue_event_id = self._create_manual_issue_event(db, snapshot=snapshot)
        first_line = (
            db.query(WorkOrderBOMSnapshotLine)
            .filter(WorkOrderBOMSnapshotLine.snapshot_id == snapshot.id)
            .order_by(WorkOrderBOMSnapshotLine.id.asc())
            .first()
        )
        assert first_line is not None
        db.add(
            StockLedger(
                org_id="ORG-1",
                ledger_no="SLED-EXISTING",
                item_id="RM-4A",
                item_code="RM-4A",
                location_id="RM-STORE",
                txn_type="ISSUE",
                movement_type="OUT",
                stock_bucket="RAW_MATERIAL",
                qty=-2.0,
                uom="PCS",
                txn_qty=2.0,
                txn_uom="PCS",
                base_qty=2.0,
                base_uom="PCS",
                ref_type="RM_ISSUE",
                ref_id=str(issue_event_id),
                source_event_type="RM_ISSUE",
                source_event_id=issue_event_id,
                source_event_line_id=first_line.id,
                work_order_id=1,
                sales_order_id=1,
                posted_by="store-a",
                posted_at=date(2026, 3, 18),
            )
        )
        db.commit()

        response = client.post(
            f"/rm-issues/{issue_event_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "duplicate line"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("source_event_line_id", response.json()["detail"])
        rows = (
            db.query(StockLedger)
            .filter(StockLedger.source_event_type == "RM_ISSUE")
            .filter(StockLedger.source_event_id == issue_event_id)
            .all()
        )
        self.assertEqual(len(rows), 1)

    def test_duplicate_guard_runs_before_item_resolution_for_each_line(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        snapshot = self._create_snapshot(
            db,
            suffix="5",
            line_defs=[
                {"item_code": "RM-5A", "required_qty": 2.0, "uom": "PCS"},
                {"item_code": "RM-5B", "required_qty": 3.0, "uom": "PCS"},
            ],
        )
        _add_item_master(db, item_code="RM-5A", unit="PCS")
        _add_item_master(db, item_code="RM-5B", unit="PCS")
        db.commit()
        issue_event_id = self._commit_issue_event(db, snapshot_id=snapshot.id)

        first = client.post(
            f"/rm-issues/{issue_event_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "first"},
        )
        self.assertEqual(first.status_code, 200)

        for code in ["RM-5A", "RM-5B"]:
            row = db.query(RawMaterial).filter(RawMaterial.material_code == code).first()
            assert row is not None
            db.delete(row)
        db.commit()

        second = client.post(
            f"/rm-issues/{issue_event_id}/post-ledger",
            json={"posted_by": "store-b", "remark": "duplicate should fail fast"},
        )

        self.assertEqual(second.status_code, 409)
        self.assertIn("Duplicate RM issue stock ledger posting is not allowed", second.json()["detail"])

    def test_item_resolution_follows_rm_issue_line_material_path(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        snapshot = self._create_snapshot(
            db,
            suffix="6",
            line_defs=[{"item_code": "RM-PATH-6", "required_qty": 2.0, "uom": "PCS"}],
        )
        _add_item_master(db, item_code="RM-PATH-6", unit="PCS")
        db.commit()
        issue_event_id = self._commit_issue_event(db, snapshot_id=snapshot.id)

        response = client.post(
            f"/rm-issues/{issue_event_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "path check"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["item_code"], "RM-PATH-6")

    def test_base_resolution_uses_sf01_conversion_rules(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        snapshot = self._create_snapshot(
            db,
            suffix="7",
            line_defs=[{"item_code": "RM-CONV-7", "required_qty": 2.0, "uom": "BOX"}],
        )
        _add_item_master(db, item_code="RM-CONV-7", unit="PCS", standard_conversion_ratio=12.0)
        db.commit()
        issue_event_id = self._commit_issue_event(db, snapshot_id=snapshot.id)

        response = client.post(
            f"/rm-issues/{issue_event_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "conversion"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.json()[0]["txn_qty"], response.json()[0]["txn_uom"]), (2.0, "BOX"))
        self.assertEqual((response.json()[0]["base_qty"], response.json()[0]["base_uom"]), (24.0, "PCS"))

    def test_missing_material_resolution_is_rejected_with_clear_detail(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        snapshot = self._create_snapshot(
            db,
            suffix="8",
            line_defs=[{"item_code": "RM-MISSING-8", "required_qty": 2.0, "uom": "PCS"}],
        )
        db.commit()
        issue_event_id = self._commit_issue_event(db, snapshot_id=snapshot.id)

        response = client.post(
            f"/rm-issues/{issue_event_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "missing material"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertIn("rm_issue_event -> rm_issue_line -> material_code -> RawMaterial.material_code", response.json()["detail"])
        self.assertIn("material_code=RM-MISSING-8", response.json()["detail"])

    def test_step_39c_does_not_modify_rm_issue_truth(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        snapshot = self._create_snapshot(
            db,
            suffix="9",
            line_defs=[{"item_code": "RM-9A", "required_qty": 2.0, "uom": "PCS"}],
        )
        _add_item_master(db, item_code="RM-9A", unit="PCS")
        db.commit()
        issue_event_id = self._commit_issue_event(db, snapshot_id=snapshot.id)
        before_snapshot = db.query(WorkOrderBOMSnapshot).filter(WorkOrderBOMSnapshot.id == snapshot.id).first()
        before_event = db.query(MaterialIssueEvent).filter(MaterialIssueEvent.issue_event_id == issue_event_id).first()
        assert before_snapshot is not None
        assert before_event is not None
        before_values = (
            before_snapshot.issue_status,
            before_snapshot.issued_by,
            before_snapshot.issued_at,
            before_event.snapshot_id,
            before_event.work_order_no,
            before_event.org_id,
            before_event.location_id,
            before_event.issued_by,
            before_event.issued_at,
        )

        response = client.post(
            f"/rm-issues/{issue_event_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "no mutate"},
        )
        self.assertEqual(response.status_code, 200)

        after_snapshot = db.query(WorkOrderBOMSnapshot).filter(WorkOrderBOMSnapshot.id == snapshot.id).first()
        after_event = db.query(MaterialIssueEvent).filter(MaterialIssueEvent.issue_event_id == issue_event_id).first()
        assert after_snapshot is not None
        assert after_event is not None
        after_values = (
            after_snapshot.issue_status,
            after_snapshot.issued_by,
            after_snapshot.issued_at,
            after_event.snapshot_id,
            after_event.work_order_no,
            after_event.org_id,
            after_event.location_id,
            after_event.issued_by,
            after_event.issued_at,
        )
        self.assertEqual(after_values, before_values)

    def test_get_returns_list_of_ledger_rows_for_rm_issue(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        snapshot = self._create_snapshot(
            db,
            suffix="10",
            line_defs=[
                {"item_code": "RM-10A", "required_qty": 1.0, "uom": "PCS"},
                {"item_code": "RM-10B", "required_qty": 2.0, "uom": "PCS"},
            ],
        )
        _add_item_master(db, item_code="RM-10A", unit="PCS")
        _add_item_master(db, item_code="RM-10B", unit="PCS")
        db.commit()
        issue_event_id = self._commit_issue_event(db, snapshot_id=snapshot.id)

        post_response = client.post(
            f"/rm-issues/{issue_event_id}/post-ledger",
            json={"posted_by": "store-a", "remark": "read me"},
        )
        self.assertEqual(post_response.status_code, 200)

        detail = client.get(f"/stock-ledger/rm-issues/{issue_event_id}")

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json(), post_response.json())


if __name__ == "__main__":
    unittest.main()
