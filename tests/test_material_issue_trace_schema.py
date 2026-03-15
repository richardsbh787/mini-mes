from __future__ import annotations

import os
import tempfile
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from database import Base
from app.bootstrap.material_issue_trace_schema import ensure_material_issue_trace_schema
from app.api.v2.work_order_material_issue_commit import work_order_material_issue_commit
from app.api.v2.work_order_material_issue_correction_commit import work_order_material_issue_correction_commit
from app.api.v2.work_order_material_issue_preview import build_material_issue_preview_from_snapshot
from app.schemas.work_order_material_issue_commit import WorkOrderMaterialIssueCommitRequest
from app.schemas.work_order_material_issue_correction_commit import WorkOrderMaterialIssueCorrectionCommitRequest
from models import MaterialIssueCorrectionEvent, MaterialIssueEvent, StockLedger, WorkOrderBOMSnapshot, WorkOrderBOMSnapshotLine


class MaterialIssueTraceSchemaTests(unittest.TestCase):
    def _new_engine(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        engine = create_engine(f"sqlite:///{path}")
        self.addCleanup(engine.dispose)
        return engine

    def test_bootstrap_creates_issue_event_table_and_stock_ledger_trace_columns(self) -> None:
        engine = self._new_engine()

        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE stock_ledger ("
                    "id INTEGER PRIMARY KEY, "
                    "org_id VARCHAR NOT NULL, "
                    "item_id VARCHAR NOT NULL, "
                    "location_id VARCHAR, "
                    "txn_type VARCHAR NOT NULL, "
                    "qty FLOAT NOT NULL, "
                    "uom VARCHAR NOT NULL, "
                    "ref_type VARCHAR, "
                    "ref_id VARCHAR, "
                    "note VARCHAR, "
                    "occurred_at DATETIME NOT NULL, "
                    "created_at DATETIME NOT NULL"
                    ")"
                )
            )

        ensure_material_issue_trace_schema(engine)

        inspector = inspect(engine)
        ledger_columns = {col["name"] for col in inspector.get_columns("stock_ledger")}
        self.assertTrue(inspector.has_table("material_issue_event"))
        self.assertTrue(inspector.has_table("material_issue_correction_event"))
        self.assertTrue({"issue_event_id", "correction_event_id", "snapshot_id", "work_order_no"}.issubset(ledger_columns))
        correction_columns = {col["name"] for col in inspector.get_columns("material_issue_correction_event")}
        self.assertTrue({"reason_code", "reason_note"}.issubset(correction_columns))


class MaterialIssueSnapshotBaselineTests(unittest.TestCase):
    def _new_engine(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        engine = create_engine(f"sqlite:///{path}")
        self.addCleanup(engine.dispose)
        return engine

    def _new_db(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        self.addCleanup(engine.dispose)
        self.addCleanup(db.close)
        return db

    def _add_snapshot_with_detail_lines(
        self,
        db,
        *,
        snapshot_id: int = 1,
        work_order_no: str = "WO-1",
        status: str = "RELEASED",
        issue_status: str = "PENDING",
        bom_version_id: int = 101,
        detail_lines: list[dict] | None = None,
    ) -> WorkOrderBOMSnapshot:
        snapshot = WorkOrderBOMSnapshot(
            id=snapshot_id,
            work_order_no=work_order_no,
            parent_system_item_code="FG-1",
            work_order_qty=2.0,
            bom_version_id=bom_version_id,
            status=status,
            issue_status=issue_status,
            created_by="planner",
        )
        db.add(snapshot)
        db.flush()

        for index, line in enumerate(detail_lines or [], start=1):
            db.add(
                WorkOrderBOMSnapshotLine(
                    snapshot_id=snapshot.id,
                    seq_no=index,
                    item_code=line["item_code"],
                    item_name=line.get("item_name"),
                    required_qty=line["required_qty"],
                    uom=line["uom"],
                )
            )

        db.commit()
        db.refresh(snapshot)
        return snapshot

    def test_preview_reads_from_persisted_snapshot_detail_baseline(self) -> None:
        db = self._new_db()
        snapshot = self._add_snapshot_with_detail_lines(
            db,
            detail_lines=[
                {"item_code": "RM-LOCKED-A", "item_name": "Locked A", "required_qty": 2.0, "uom": "PCS"},
                {"item_code": "RM-LOCKED-B", "item_name": None, "required_qty": 5.0, "uom": "KG"},
            ],
        )

        result = build_material_issue_preview_from_snapshot(snapshot=snapshot, db=db)

        self.assertEqual(
            result["issue_lines"],
            [
                {"item_code": "RM-LOCKED-A", "item_name": "Locked A", "required_qty": 2.0, "uom": "PCS"},
                {"item_code": "RM-LOCKED-B", "item_name": None, "required_qty": 5.0, "uom": "KG"},
            ],
        )

    def test_issue_commit_uses_persisted_snapshot_detail_baseline_without_bom_reexplosion(self) -> None:
        db = self._new_db()
        snapshot = self._add_snapshot_with_detail_lines(
            db,
            detail_lines=[
                {"item_code": "RM-LOCKED-A", "item_name": "Locked A", "required_qty": 2.0, "uom": "PCS"},
                {"item_code": "RM-LOCKED-B", "item_name": None, "required_qty": 5.0, "uom": "KG"},
            ],
        )

        result = work_order_material_issue_commit(
            payload=WorkOrderMaterialIssueCommitRequest(
                snapshot_id=snapshot.id,
                org_id="ORG-1",
                location_id="RM-STORE",
                issued_by="store",
            ),
            db=db,
        )

        issue_event = db.query(MaterialIssueEvent).one()
        ledger_rows = db.query(StockLedger).order_by(StockLedger.id.asc()).all()
        db.refresh(snapshot)

        self.assertEqual(result["issue_status"], "ISSUED")
        self.assertEqual(snapshot.issue_status, "ISSUED")
        self.assertEqual(issue_event.snapshot_id, snapshot.id)
        self.assertEqual(
            [(row.item_id, row.qty, row.uom, row.issue_event_id, row.snapshot_id, row.work_order_no) for row in ledger_rows],
            [
                ("RM-LOCKED-A", 2.0, "PCS", issue_event.issue_event_id, snapshot.id, snapshot.work_order_no),
                ("RM-LOCKED-B", 5.0, "KG", issue_event.issue_event_id, snapshot.id, snapshot.work_order_no),
            ],
        )

    def test_issue_gating_remains_intact_when_snapshot_not_issueable(self) -> None:
        db = self._new_db()
        draft_snapshot = self._add_snapshot_with_detail_lines(
            db,
            snapshot_id=1,
            work_order_no="WO-DRAFT",
            status="DRAFT",
            detail_lines=[{"item_code": "RM-1", "required_qty": 1.0, "uom": "PCS"}],
        )
        issued_snapshot = self._add_snapshot_with_detail_lines(
            db,
            snapshot_id=2,
            work_order_no="WO-ISSUED",
            status="RELEASED",
            issue_status="ISSUED",
            detail_lines=[{"item_code": "RM-2", "required_qty": 1.0, "uom": "PCS"}],
        )

        with self.assertRaises(HTTPException) as preview_exc:
            build_material_issue_preview_from_snapshot(snapshot=draft_snapshot, db=db)
        self.assertEqual(preview_exc.exception.status_code, 409)
        self.assertEqual(preview_exc.exception.detail, f"Snapshot is DRAFT and cannot preview material issue: id={draft_snapshot.id}")

        with self.assertRaises(HTTPException) as commit_exc:
            work_order_material_issue_commit(
                payload=WorkOrderMaterialIssueCommitRequest(
                    snapshot_id=issued_snapshot.id,
                    org_id="ORG-1",
                    location_id="RM-STORE",
                    issued_by="store",
                ),
                db=db,
            )
        self.assertEqual(commit_exc.exception.status_code, 409)
        self.assertEqual(
            commit_exc.exception.detail,
            f"Snapshot already ISSUED and cannot commit material issue: id={issued_snapshot.id}",
        )

    def test_correction_commit_works_from_committed_issue_trace_without_bom_calculation(self) -> None:
        db = self._new_db()
        snapshot = self._add_snapshot_with_detail_lines(
            db,
            status="RELEASED",
            issue_status="ISSUED",
            detail_lines=[{"item_code": "RM-LOCKED-A", "required_qty": 2.0, "uom": "PCS"}],
        )

        issue_event = MaterialIssueEvent(
            snapshot_id=snapshot.id,
            work_order_no=snapshot.work_order_no,
            bom_version_id=snapshot.bom_version_id,
            org_id="ORG-1",
            location_id="RM-STORE",
            issued_by="store",
        )
        db.add(issue_event)
        db.flush()
        db.add(
            StockLedger(
                org_id="ORG-1",
                item_id="RM-LOCKED-A",
                location_id="RM-STORE",
                txn_type="ISSUE",
                qty=2.0,
                uom="PCS",
                ref_type="WORK_ORDER_BOM_SNAPSHOT",
                ref_id=str(snapshot.id),
                note=snapshot.work_order_no,
                issue_event_id=issue_event.issue_event_id,
                snapshot_id=snapshot.id,
                work_order_no=snapshot.work_order_no,
            )
        )
        db.commit()

        result = work_order_material_issue_correction_commit(
            payload=WorkOrderMaterialIssueCorrectionCommitRequest(
                original_issue_event_id=issue_event.issue_event_id,
                reason_code="WRONG_QTY",
                corrected_by="auditor",
            ),
            db=db,
        )

        correction_event = db.query(MaterialIssueCorrectionEvent).one()
        ledger_rows = db.query(StockLedger).order_by(StockLedger.id.asc()).all()

        self.assertEqual(result["original_issue_event_id"], issue_event.issue_event_id)
        self.assertEqual(correction_event.original_issue_event_id, issue_event.issue_event_id)
        self.assertEqual(len(ledger_rows), 2)
        self.assertEqual(ledger_rows[0].txn_type, "ISSUE")
        self.assertEqual(ledger_rows[1].txn_type, "RECEIPT")
        self.assertEqual(ledger_rows[1].correction_event_id, correction_event.correction_event_id)

    def test_bootstrap_is_idempotent_for_existing_trace_schema(self) -> None:
        engine = self._new_engine()

        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE material_issue_event ("
                    "issue_event_id INTEGER PRIMARY KEY, "
                    "snapshot_id INTEGER NOT NULL, "
                    "work_order_no VARCHAR NOT NULL, "
                    "bom_version_id INTEGER NOT NULL, "
                    "org_id VARCHAR NOT NULL, "
                    "location_id VARCHAR NOT NULL, "
                    "issued_by VARCHAR NOT NULL, "
                    "issued_at DATETIME NOT NULL"
                    ")"
                )
            )
            conn.execute(
                text(
                    "CREATE TABLE material_issue_correction_event ("
                    "correction_event_id INTEGER PRIMARY KEY, "
                    "original_issue_event_id INTEGER NOT NULL, "
                    "snapshot_id INTEGER NOT NULL, "
                    "work_order_no VARCHAR NOT NULL, "
                    "org_id VARCHAR NOT NULL, "
                    "location_id VARCHAR NOT NULL, "
                    "reason_code VARCHAR NOT NULL, "
                    "reason_note VARCHAR, "
                    "corrected_by VARCHAR NOT NULL, "
                    "corrected_at DATETIME NOT NULL"
                    ")"
                )
            )
            conn.execute(
                text(
                    "CREATE TABLE stock_ledger ("
                    "id INTEGER PRIMARY KEY, "
                    "org_id VARCHAR NOT NULL, "
                    "item_id VARCHAR NOT NULL, "
                    "location_id VARCHAR, "
                    "txn_type VARCHAR NOT NULL, "
                    "qty FLOAT NOT NULL, "
                    "uom VARCHAR NOT NULL, "
                    "ref_type VARCHAR, "
                    "ref_id VARCHAR, "
                    "note VARCHAR, "
                    "issue_event_id INTEGER, "
                    "correction_event_id INTEGER, "
                    "snapshot_id INTEGER, "
                    "work_order_no VARCHAR, "
                    "occurred_at DATETIME NOT NULL, "
                    "created_at DATETIME NOT NULL"
                    ")"
                )
            )

        ensure_material_issue_trace_schema(engine)
        ensure_material_issue_trace_schema(engine)

        inspector = inspect(engine)
        ledger_columns = {col["name"] for col in inspector.get_columns("stock_ledger")}
        self.assertTrue(inspector.has_table("material_issue_event"))
        self.assertTrue(inspector.has_table("material_issue_correction_event"))
        self.assertTrue({"issue_event_id", "correction_event_id", "snapshot_id", "work_order_no"}.issubset(ledger_columns))
        correction_columns = {col["name"] for col in inspector.get_columns("material_issue_correction_event")}
        self.assertTrue({"reason_code", "reason_note"}.issubset(correction_columns))


if __name__ == "__main__":
    unittest.main()
