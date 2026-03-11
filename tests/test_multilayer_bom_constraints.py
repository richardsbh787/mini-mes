from __future__ import annotations

from datetime import date, timedelta

import unittest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from pydantic import ValidationError

from database import Base
from models import BOMHeader, BOMLine, BOMVersion, MaterialIssueCorrectionEvent, MaterialIssueEvent, StockLedger, WorkOrderBOMSnapshot
from app.api.v2.work_order_bom_bind import work_order_bom_bind
from app.api.v2.work_order_bom_preview import build_work_order_bom_preview
from app.api.v2.work_order_bom_release import work_order_bom_release
from app.api.v2.work_order_material_issue_commit import work_order_material_issue_commit
from app.api.v2.work_order_material_issue_correction_commit import work_order_material_issue_correction_commit
from app.api.v2.work_order_material_issue_preview import build_material_issue_preview_from_snapshot
from app.schemas.work_order_bom_bind import WorkOrderBOMBindRequest
from app.schemas.work_order_bom_release import WorkOrderBOMReleaseRequest
from app.schemas.work_order_material_issue_commit import WorkOrderMaterialIssueCommitRequest
from app.schemas.work_order_material_issue_correction_commit import WorkOrderMaterialIssueCorrectionCommitRequest
from app.services.bom_flat_explosion_service import BOMFlatExplosionService
from app.services.bom_tree_explosion_service import BOMTreeExplosionService


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


def _add_header(db: Session, parent_code: str, status: str = "ACTIVE") -> BOMHeader:
    row = BOMHeader(
        parent_system_item_code=parent_code,
        bom_type="STD",
        status=status,
        created_by="test",
    )
    db.add(row)
    db.flush()
    return row


def _add_version(
    db: Session,
    bom_id: int,
    status: str = "ACTIVE",
    effective_from: date | None = None,
    effective_to: date | None = None,
) -> BOMVersion:
    row = BOMVersion(
        bom_id=bom_id,
        bom_revision="R1",
        status=status,
        effective_from=effective_from,
        effective_to=effective_to,
        created_by="test",
    )
    db.add(row)
    db.flush()
    return row


def _add_line(
    db: Session,
    version_id: int,
    sequence: int,
    component_code: str,
    qty_per: float,
    uom: str = "PCS",
    scrap_rate: float = 0.0,
    phantom_flag: bool = False,
) -> BOMLine:
    row = BOMLine(
        version_id=version_id,
        sequence=sequence,
        component_system_item_code=component_code,
        qty_per=qty_per,
        uom=uom,
        scrap_rate=scrap_rate,
        phantom_flag=phantom_flag,
    )
    db.add(row)
    db.flush()
    return row


class MultilayerBOMConstraintsTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def test_tree_explosion_retains_phantom_node_and_recurse_children(self) -> None:
        db = self._new_db()
        svc = BOMTreeExplosionService()

        fg = _add_header(db, "FG-1")
        fg_v = _add_version(db, fg.bom_id)
        _add_line(db, fg_v.version_id, sequence=10, component_code="PH-1", qty_per=2.0, phantom_flag=True)

        phantom = _add_header(db, "PH-1")
        phantom_v = _add_version(db, phantom.bom_id)
        _add_line(db, phantom_v.version_id, sequence=10, component_code="RM-1", qty_per=3.0)
        db.commit()

        result = svc.explode_tree(db=db, parent_system_item_code="FG-1", required_qty=5.0, version_id=fg_v.version_id)
        phantom_node = result["tree"]["children"][0]

        self.assertTrue(phantom_node["is_phantom"])
        self.assertFalse(phantom_node["is_leaf"])
        self.assertEqual(phantom_node["required_qty"], 10.0)
        self.assertEqual(
            phantom_node["children"],
            [
                {
                    "item_code": "RM-1",
                    "item_name": None,
                    "required_qty": 30.0,
                    "uom": "PCS",
                    "level": 2,
                    "path": ["FG-1", "PH-1", "RM-1"],
                    "is_phantom": False,
                    "is_leaf": True,
                    "children": [],
                }
            ],
        )

    def test_flat_explosion_skips_phantom_with_no_child_bom(self) -> None:
        db = self._new_db()
        svc = BOMFlatExplosionService()

        root = _add_header(db, "FG-1")
        root_v = _add_version(db, root.bom_id)
        _add_line(db, root_v.version_id, sequence=10, component_code="RM-1", qty_per=2.0)
        _add_line(db, root_v.version_id, sequence=20, component_code="PH-1", qty_per=5.0, phantom_flag=True)
        db.commit()

        rows = svc.explode_flat(db=db, parent_system_item_code="FG-1", required_qty=3.0, version_id=root_v.version_id)
        self.assertEqual(
            rows,
            [
                {
                    "item_code": "RM-1",
                    "item_name": None,
                    "total_qty": 6.0,
                    "uom": "PCS",
                }
            ],
        )

    def test_flat_explosion_detects_cycle_with_full_path(self) -> None:
        db = self._new_db()
        svc = BOMFlatExplosionService()

        a = _add_header(db, "A")
        a_v = _add_version(db, a.bom_id)
        _add_line(db, a_v.version_id, sequence=10, component_code="B", qty_per=1.0)

        b = _add_header(db, "B")
        b_v = _add_version(db, b.bom_id)
        _add_line(db, b_v.version_id, sequence=10, component_code="A", qty_per=1.0)
        db.commit()

        with self.assertRaises(HTTPException) as exc:
            svc.explode_flat(db=db, parent_system_item_code="A", required_qty=1.0, version_id=a_v.version_id)

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(exc.exception.detail, "Cycle detected: A -> B -> A")

    def test_explicit_version_id_is_still_validated(self) -> None:
        db = self._new_db()
        svc = BOMFlatExplosionService()

        fg1 = _add_header(db, "FG-1")
        fg2 = _add_header(db, "FG-2")
        fg1_v = _add_version(db, fg1.bom_id)
        fg2_v = _add_version(db, fg2.bom_id)
        _add_line(db, fg1_v.version_id, sequence=10, component_code="RM-1", qty_per=1.0)
        db.commit()

        with self.assertRaises(HTTPException) as wrong_bom:
            svc.explode_flat(db=db, parent_system_item_code="FG-1", required_qty=1.0, version_id=fg2_v.version_id)
        self.assertEqual(wrong_bom.exception.status_code, 404)

        draft_v = _add_version(db, fg1.bom_id, status="DRAFT")
        db.commit()
        with self.assertRaises(HTTPException) as not_active:
            svc.explode_flat(db=db, parent_system_item_code="FG-1", required_qty=1.0, version_id=draft_v.version_id)
        self.assertEqual(not_active.exception.status_code, 400)
        self.assertEqual(not_active.exception.detail, "BOM version is not ACTIVE")

        future_v = _add_version(
            db,
            fg1.bom_id,
            status="ACTIVE",
            effective_from=date.today() + timedelta(days=30),
        )
        db.commit()
        with self.assertRaises(HTTPException) as not_effective:
            svc.explode_flat(db=db, parent_system_item_code="FG-1", required_qty=1.0, version_id=future_v.version_id)
        self.assertEqual(not_effective.exception.status_code, 404)

    def test_material_issue_preview_uses_snapshot_version_lock(self) -> None:
        db = self._new_db()

        root = _add_header(db, "FG-1")
        locked_v = _add_version(db, root.bom_id)
        _add_line(db, locked_v.version_id, sequence=10, component_code="RM-LOCKED", qty_per=1.0)

        newer_v = _add_version(db, root.bom_id)
        _add_line(db, newer_v.version_id, sequence=10, component_code="RM-NEW", qty_per=1.0)

        snapshot = WorkOrderBOMSnapshot(
            work_order_no="WO-LOCK-1",
            parent_system_item_code="FG-1",
            work_order_qty=2.0,
            bom_version_id=locked_v.version_id,
            status="RELEASED",
            issue_status="PENDING",
            created_by="test",
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        preview = build_material_issue_preview_from_snapshot(snapshot=snapshot, db=db)
        self.assertEqual(preview["bom_version_id"], locked_v.version_id)
        self.assertEqual(
            preview["issue_lines"],
            [
                {
                    "item_code": "RM-LOCKED",
                    "item_name": None,
                    "required_qty": 2.0,
                    "uom": "PCS",
                }
            ],
        )
        self.assertEqual(db.query(MaterialIssueEvent).count(), 0)
        self.assertEqual(db.query(MaterialIssueCorrectionEvent).count(), 0)
        self.assertEqual(db.query(StockLedger).count(), 0)

    def test_work_order_preview_is_read_only_and_does_not_write_ledger(self) -> None:
        db = self._new_db()

        root = _add_header(db, "FG-1")
        root_v = _add_version(db, root.bom_id)
        _add_line(db, root_v.version_id, sequence=10, component_code="RM-1", qty_per=2.0)
        db.commit()

        preview = build_work_order_bom_preview(
            db=db,
            parent_system_item_code="FG-1",
            work_order_qty=4.0,
            version_id=root_v.version_id,
        )

        self.assertEqual(preview["version_id"], root_v.version_id)
        self.assertEqual(
            db.query(StockLedger).count(),
            0,
        )
        self.assertEqual(
            preview["flat_materials"],
            [
                {
                    "item_code": "RM-1",
                    "item_name": None,
                    "total_qty": 8.0,
                    "uom": "PCS",
                }
            ],
        )

    def test_work_order_bind_rejects_duplicate_work_order_no(self) -> None:
        db = self._new_db()

        root = _add_header(db, "FG-1")
        root_v = _add_version(db, root.bom_id)
        _add_line(db, root_v.version_id, sequence=10, component_code="RM-1", qty_per=1.0)
        db.commit()

        first = work_order_bom_bind(
            payload=WorkOrderBOMBindRequest(
                work_order_no="WO-DUP-1",
                parent_system_item_code="FG-1",
                work_order_qty=2.0,
                version_id=root_v.version_id,
                created_by="planner",
            ),
            db=db,
        )
        self.assertEqual(first["version_id"], root_v.version_id)

        with self.assertRaises(HTTPException) as exc:
            work_order_bom_bind(
                payload=WorkOrderBOMBindRequest(
                    work_order_no="WO-DUP-1",
                    parent_system_item_code="FG-1",
                    work_order_qty=2.0,
                    version_id=root_v.version_id,
                    created_by="planner",
                ),
                db=db,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "Snapshot already exists for work_order_no=WO-DUP-1",
        )

    def test_work_order_release_rejects_non_draft_statuses(self) -> None:
        db = self._new_db()

        for snapshot_status, expected_detail in [
            ("RELEASED", "Snapshot already RELEASED: id=1"),
            ("VOID", "Snapshot is VOID and cannot be released: id=1"),
            ("CLOSED", "Snapshot status CLOSED cannot be released (only DRAFT allowed): id=1"),
        ]:
            db.query(WorkOrderBOMSnapshot).delete()
            snapshot = WorkOrderBOMSnapshot(
                id=1,
                work_order_no=f"WO-{snapshot_status}",
                parent_system_item_code="FG-1",
                work_order_qty=1.0,
                bom_version_id=100,
                status=snapshot_status,
                issue_status="PENDING",
                created_by="test",
            )
            db.add(snapshot)
            db.commit()

            with self.assertRaises(HTTPException) as exc:
                work_order_bom_release(
                    payload=WorkOrderBOMReleaseRequest(snapshot_id=1, released_by="planner"),
                    db=db,
                )

            self.assertEqual(exc.exception.status_code, 409)
            self.assertEqual(exc.exception.detail, expected_detail)

    def test_material_issue_preview_rejects_non_released_statuses(self) -> None:
        db = self._new_db()

        for snapshot_status, expected_detail in [
            ("DRAFT", "Snapshot is DRAFT and cannot preview material issue: id=1"),
            ("VOID", "Snapshot is VOID and cannot preview material issue: id=1"),
            (
                "CLOSED",
                "Snapshot status CLOSED cannot preview material issue (only RELEASED allowed): id=1",
            ),
        ]:
            db.query(WorkOrderBOMSnapshot).delete()
            snapshot = WorkOrderBOMSnapshot(
                id=1,
                work_order_no=f"WO-{snapshot_status}",
                parent_system_item_code="FG-1",
                work_order_qty=1.0,
                bom_version_id=100,
                status=snapshot_status,
                issue_status="PENDING",
                created_by="test",
            )
            db.add(snapshot)
            db.commit()

            with self.assertRaises(HTTPException) as exc:
                build_material_issue_preview_from_snapshot(snapshot=snapshot, db=db)

            self.assertEqual(exc.exception.status_code, 409)
            self.assertEqual(exc.exception.detail, expected_detail)

    def test_material_issue_preview_rejects_non_pending_issue_statuses(self) -> None:
        db = self._new_db()

        root = _add_header(db, "FG-1")
        root_v = _add_version(db, root.bom_id)
        _add_line(db, root_v.version_id, sequence=10, component_code="RM-1", qty_per=1.0)
        db.commit()

        for issue_status, expected_detail in [
            ("ISSUED", "Snapshot already ISSUED and cannot preview material issue: id=1"),
            ("VOID", "Snapshot issue_status VOID cannot preview material issue: id=1"),
            ("CLOSED", "Snapshot issue_status CLOSED cannot preview material issue: id=1"),
            ("UNKNOWN", "Snapshot issue_status UNKNOWN cannot preview material issue: id=1"),
        ]:
            db.query(WorkOrderBOMSnapshot).delete()
            snapshot = WorkOrderBOMSnapshot(
                id=1,
                work_order_no=f"WO-{issue_status}",
                parent_system_item_code="FG-1",
                work_order_qty=1.0,
                bom_version_id=root_v.version_id,
                status="RELEASED",
                issue_status=issue_status,
                created_by="test",
            )
            db.add(snapshot)
            db.commit()

            with self.assertRaises(HTTPException) as exc:
                build_material_issue_preview_from_snapshot(snapshot=snapshot, db=db)

            self.assertEqual(exc.exception.status_code, 409)
            self.assertEqual(exc.exception.detail, expected_detail)

    def test_material_issue_commit_rejects_non_pending_issue_statuses(self) -> None:
        db = self._new_db()

        root = _add_header(db, "FG-1")
        root_v = _add_version(db, root.bom_id)
        _add_line(db, root_v.version_id, sequence=10, component_code="RM-1", qty_per=1.0)
        db.commit()

        for issue_status, expected_detail in [
            ("ISSUED", "Snapshot already ISSUED and cannot commit material issue: id=1"),
            ("VOID", "Snapshot issue_status VOID cannot commit material issue: id=1"),
            ("CLOSED", "Snapshot issue_status CLOSED cannot commit material issue: id=1"),
            ("UNKNOWN", "Snapshot issue_status UNKNOWN cannot commit material issue: id=1"),
        ]:
            db.query(StockLedger).delete()
            db.query(WorkOrderBOMSnapshot).delete()
            snapshot = WorkOrderBOMSnapshot(
                id=1,
                work_order_no=f"WO-COMMIT-{issue_status}",
                parent_system_item_code="FG-1",
                work_order_qty=1.0,
                bom_version_id=root_v.version_id,
                status="RELEASED",
                issue_status=issue_status,
                created_by="test",
            )
            db.add(snapshot)
            db.commit()

            with self.assertRaises(HTTPException) as exc:
                work_order_material_issue_commit(
                    payload=WorkOrderMaterialIssueCommitRequest(
                        snapshot_id=1,
                        org_id="ORG-1",
                        location_id="RM-STORE",
                        issued_by="store",
                    ),
                    db=db,
                )

            self.assertEqual(exc.exception.status_code, 409)
            self.assertEqual(exc.exception.detail, expected_detail)
            self.assertEqual(db.query(StockLedger).count(), 0)
            self.assertEqual(db.query(MaterialIssueEvent).count(), 0)
            self.assertEqual(db.query(MaterialIssueCorrectionEvent).count(), 0)

    def test_material_issue_commit_rolls_back_ledger_and_issue_status_on_failure(self) -> None:
        db = self._new_db()

        root = _add_header(db, "FG-1")
        root_v = _add_version(db, root.bom_id)
        _add_line(db, root_v.version_id, sequence=10, component_code="RM-1", qty_per=2.0)

        snapshot = WorkOrderBOMSnapshot(
            work_order_no="WO-ROLLBACK-1",
            parent_system_item_code="FG-1",
            work_order_qty=3.0,
            bom_version_id=root_v.version_id,
            status="RELEASED",
            issue_status="PENDING",
            created_by="test",
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        original_commit = db.commit

        def fail_commit():
            raise RuntimeError("boom")

        db.commit = fail_commit
        try:
            with self.assertRaises(HTTPException) as exc:
                work_order_material_issue_commit(
                    payload=WorkOrderMaterialIssueCommitRequest(
                        snapshot_id=snapshot.id,
                        org_id="ORG-1",
                        location_id="RM-STORE",
                        issued_by="store",
                    ),
                    db=db,
                )
        finally:
            db.commit = original_commit

        self.assertEqual(exc.exception.status_code, 500)
        self.assertEqual(
            exc.exception.detail,
            f"Material issue commit failed and rolled back: id={snapshot.id}",
        )
        self.assertEqual(db.query(MaterialIssueEvent).count(), 0)
        self.assertEqual(db.query(MaterialIssueCorrectionEvent).count(), 0)
        self.assertEqual(db.query(StockLedger).count(), 0)
        db.refresh(snapshot)
        self.assertEqual(snapshot.issue_status, "PENDING")

    def test_material_issue_preview_response_schema_remains_unchanged(self) -> None:
        db = self._new_db()

        root = _add_header(db, "FG-1")
        root_v = _add_version(db, root.bom_id)
        _add_line(db, root_v.version_id, sequence=10, component_code="RM-1", qty_per=1.0)

        snapshot = WorkOrderBOMSnapshot(
            work_order_no="WO-SCHEMA-1",
            parent_system_item_code="FG-1",
            work_order_qty=2.0,
            bom_version_id=root_v.version_id,
            status="RELEASED",
            issue_status="PENDING",
            created_by="test",
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        preview = build_material_issue_preview_from_snapshot(snapshot=snapshot, db=db)

        self.assertEqual(
            set(preview.keys()),
            {
                "snapshot_id",
                "work_order_no",
                "parent_system_item_code",
                "work_order_qty",
                "bom_version_id",
                "status",
                "issue_lines",
            },
        )
        self.assertEqual(db.query(MaterialIssueEvent).count(), 0)
        self.assertEqual(db.query(MaterialIssueCorrectionEvent).count(), 0)
        self.assertEqual(db.query(StockLedger).count(), 0)

    def test_release_then_commit_writes_ledger_only_in_commit_layer(self) -> None:
        db = self._new_db()

        root = _add_header(db, "FG-1")
        root_v = _add_version(db, root.bom_id)
        _add_line(db, root_v.version_id, sequence=10, component_code="RM-1", qty_per=2.0)

        snapshot = WorkOrderBOMSnapshot(
            work_order_no="WO-1",
            parent_system_item_code="FG-1",
            work_order_qty=3.0,
            bom_version_id=root_v.version_id,
            status="DRAFT",
            issue_status="PENDING",
            created_by="test",
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

        release_result = work_order_bom_release(
            payload=WorkOrderBOMReleaseRequest(snapshot_id=snapshot.id, released_by="planner"),
            db=db,
        )
        self.assertEqual(release_result["status"], "RELEASED")
        self.assertEqual(db.query(StockLedger).count(), 0)

        commit_result = work_order_material_issue_commit(
            payload=WorkOrderMaterialIssueCommitRequest(
                snapshot_id=snapshot.id,
                org_id="ORG-1",
                location_id="RM-STORE",
                issued_by="store",
            ),
            db=db,
        )

        self.assertEqual(commit_result["status"], "RELEASED")
        self.assertEqual(commit_result["issue_status"], "ISSUED")
        self.assertEqual(
            commit_result["ledger_rows"],
            [
                {
                    "item_code": "RM-1",
                    "qty": 6.0,
                    "uom": "PCS",
                    "txn_type": "ISSUE",
                }
            ],
        )

        ledger_rows = db.query(StockLedger).all()
        issue_events = db.query(MaterialIssueEvent).all()
        self.assertEqual(len(issue_events), 1)
        self.assertEqual(issue_events[0].snapshot_id, snapshot.id)
        self.assertEqual(issue_events[0].work_order_no, snapshot.work_order_no)
        self.assertEqual(issue_events[0].bom_version_id, snapshot.bom_version_id)
        self.assertEqual(issue_events[0].org_id, "ORG-1")
        self.assertEqual(issue_events[0].location_id, "RM-STORE")
        self.assertEqual(issue_events[0].issued_by, "store")
        self.assertEqual(len(ledger_rows), 1)
        self.assertEqual(ledger_rows[0].txn_type, "ISSUE")
        self.assertEqual(ledger_rows[0].item_id, "RM-1")
        self.assertEqual(ledger_rows[0].qty, 6.0)
        self.assertEqual(ledger_rows[0].ref_type, "WORK_ORDER_BOM_SNAPSHOT")
        self.assertEqual(ledger_rows[0].ref_id, str(snapshot.id))
        self.assertEqual(ledger_rows[0].issue_event_id, issue_events[0].issue_event_id)
        self.assertIsNone(ledger_rows[0].correction_event_id)
        self.assertEqual(ledger_rows[0].snapshot_id, snapshot.id)
        self.assertEqual(ledger_rows[0].work_order_no, snapshot.work_order_no)

    def test_material_issue_correction_preserves_original_history_and_adds_compensating_rows(self) -> None:
        db = self._new_db()

        root = _add_header(db, "FG-1")
        root_v = _add_version(db, root.bom_id)
        _add_line(db, root_v.version_id, sequence=10, component_code="RM-1", qty_per=2.0)

        snapshot = WorkOrderBOMSnapshot(
            work_order_no="WO-CORR-1",
            parent_system_item_code="FG-1",
            work_order_qty=3.0,
            bom_version_id=root_v.version_id,
            status="RELEASED",
            issue_status="ISSUED",
            created_by="test",
            issued_by="store",
        )
        db.add(snapshot)
        db.commit()
        db.refresh(snapshot)

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

        original_ledger = StockLedger(
            org_id="ORG-1",
            item_id="RM-1",
            location_id="RM-STORE",
            txn_type="ISSUE",
            qty=6.0,
            uom="PCS",
            ref_type="WORK_ORDER_BOM_SNAPSHOT",
            ref_id=str(snapshot.id),
            note=snapshot.work_order_no,
            issue_event_id=issue_event.issue_event_id,
            snapshot_id=snapshot.id,
            work_order_no=snapshot.work_order_no,
        )
        db.add(original_ledger)
        db.commit()
        db.refresh(issue_event)
        db.refresh(original_ledger)

        result = work_order_material_issue_correction_commit(
            payload=WorkOrderMaterialIssueCorrectionCommitRequest(
                original_issue_event_id=issue_event.issue_event_id,
                reason_code="WRONG_QTY",
                corrected_by="auditor",
            ),
            db=db,
        )

        self.assertEqual(result["original_issue_event_id"], issue_event.issue_event_id)
        correction_events = db.query(MaterialIssueCorrectionEvent).all()
        self.assertEqual(len(correction_events), 1)
        self.assertEqual(correction_events[0].original_issue_event_id, issue_event.issue_event_id)
        self.assertEqual(correction_events[0].snapshot_id, snapshot.id)
        self.assertEqual(correction_events[0].work_order_no, snapshot.work_order_no)
        self.assertEqual(correction_events[0].reason_code, "WRONG_QTY")
        self.assertIsNone(correction_events[0].reason_note)
        self.assertEqual(correction_events[0].corrected_by, "auditor")

        db.refresh(snapshot)
        db.refresh(issue_event)
        db.refresh(original_ledger)
        self.assertEqual(snapshot.issue_status, "ISSUED")
        self.assertEqual(issue_event.issued_by, "store")
        self.assertEqual(original_ledger.txn_type, "ISSUE")
        self.assertEqual(original_ledger.qty, 6.0)
        self.assertEqual(original_ledger.issue_event_id, issue_event.issue_event_id)
        self.assertIsNone(original_ledger.correction_event_id)

        ledger_rows = db.query(StockLedger).order_by(StockLedger.id.asc()).all()
        self.assertEqual(len(ledger_rows), 2)
        self.assertEqual(ledger_rows[1].txn_type, "RECEIPT")
        self.assertEqual(ledger_rows[1].qty, 6.0)
        self.assertEqual(ledger_rows[1].item_id, "RM-1")
        self.assertEqual(ledger_rows[1].issue_event_id, None)
        self.assertEqual(ledger_rows[1].correction_event_id, correction_events[0].correction_event_id)
        self.assertEqual(ledger_rows[1].snapshot_id, snapshot.id)
        self.assertEqual(ledger_rows[1].work_order_no, snapshot.work_order_no)

    def test_material_issue_correction_lookup_by_original_issue_event_id(self) -> None:
        db = self._new_db()

        correction = MaterialIssueCorrectionEvent(
            correction_event_id=11,
            original_issue_event_id=7,
            snapshot_id=3,
            work_order_no="WO-CORR-LOOKUP-1",
            org_id="ORG-1",
            location_id="RM-STORE",
            reason_code="WRONG_QTY",
            reason_note="operator reversal",
            corrected_by="auditor",
        )
        db.add(correction)
        db.commit()

        result = get_material_issue_correction(original_issue_event_id=7, db=db)

        self.assertEqual(
            result,
            {
                "correction_event_id": 11,
                "original_issue_event_id": 7,
                "snapshot_id": 3,
                "work_order_no": "WO-CORR-LOOKUP-1",
                "reason_code": "WRONG_QTY",
                "reason_note": "operator reversal",
                "corrected_by": "auditor",
                "corrected_at": correction.corrected_at,
            },
        )

    def test_material_issue_correction_lookup_returns_not_found_when_missing(self) -> None:
        db = self._new_db()

        with self.assertRaises(HTTPException) as exc:
            get_material_issue_correction(original_issue_event_id=99, db=db)

        self.assertEqual(exc.exception.status_code, 404)
        self.assertEqual(exc.exception.detail, "Correction not found for original_issue_event_id=99")

    def test_material_issue_correction_lookup_rejects_nonpositive_issue_event_id(self) -> None:
        db = self._new_db()

        with self.assertRaises(HTTPException) as exc:
            get_material_issue_correction(original_issue_event_id=0, db=db)

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(exc.exception.detail, "original_issue_event_id must be > 0")

    def test_material_issue_correction_lookup_response_contract_is_minimal_and_stable(self) -> None:
        db = self._new_db()

        correction = MaterialIssueCorrectionEvent(
            correction_event_id=15,
            original_issue_event_id=8,
            snapshot_id=4,
            work_order_no="WO-CORR-CONTRACT-1",
            org_id="ORG-1",
            location_id="RM-STORE",
            reason_code="OTHER",
            reason_note="manual note",
            corrected_by="auditor",
        )
        db.add(correction)
        db.commit()

        result = get_material_issue_correction(original_issue_event_id=8, db=db)

        self.assertEqual(
            set(result.keys()),
            {
                "correction_event_id",
                "original_issue_event_id",
                "snapshot_id",
                "work_order_no",
                "reason_code",
                "reason_note",
                "corrected_by",
                "corrected_at",
            },
        )

    def test_material_issue_correction_lookup_is_read_only(self) -> None:
        db = self._new_db()

        snapshot = WorkOrderBOMSnapshot(
            id=1,
            work_order_no="WO-CORR-READ-ONLY-1",
            parent_system_item_code="FG-1",
            work_order_qty=1.0,
            bom_version_id=1,
            status="RELEASED",
            issue_status="ISSUED",
            created_by="test",
        )
        issue_event = MaterialIssueEvent(
            issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-READ-ONLY-1",
            bom_version_id=1,
            org_id="ORG-1",
            location_id="RM-STORE",
            issued_by="store",
        )
        correction = MaterialIssueCorrectionEvent(
            correction_event_id=1,
            original_issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-READ-ONLY-1",
            org_id="ORG-1",
            location_id="RM-STORE",
            reason_code="WRONG_ITEM",
            reason_note=None,
            corrected_by="auditor",
        )
        ledger = StockLedger(
            org_id="ORG-1",
            item_id="RM-1",
            location_id="RM-STORE",
            txn_type="ISSUE",
            qty=1.0,
            uom="PCS",
            issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-READ-ONLY-1",
        )
        db.add(snapshot)
        db.add(issue_event)
        db.add(correction)
        db.add(ledger)
        db.commit()

        before_snapshot_status = db.query(WorkOrderBOMSnapshot).filter(WorkOrderBOMSnapshot.id == 1).one().issue_status
        before_issue_count = db.query(MaterialIssueEvent).count()
        before_correction_count = db.query(MaterialIssueCorrectionEvent).count()
        before_ledger_count = db.query(StockLedger).count()

        result = get_material_issue_correction(original_issue_event_id=1, db=db)

        self.assertEqual(result["correction_event_id"], 1)
        self.assertEqual(db.query(MaterialIssueEvent).count(), before_issue_count)
        self.assertEqual(db.query(MaterialIssueCorrectionEvent).count(), before_correction_count)
        self.assertEqual(db.query(StockLedger).count(), before_ledger_count)
        self.assertEqual(
            db.query(WorkOrderBOMSnapshot).filter(WorkOrderBOMSnapshot.id == 1).one().issue_status,
            before_snapshot_status,
        )
    def test_material_issue_correction_list_returns_minimal_field_contract(self) -> None:
        db = self._new_db()

        correction = MaterialIssueCorrectionEvent(
            correction_event_id=21,
            original_issue_event_id=12,
            snapshot_id=4,
            work_order_no="WO-CORR-LIST-1",
            org_id="ORG-1",
            location_id="RM-STORE",
            reason_code="WRONG_QTY",
            reason_note="manual trace",
            corrected_by="auditor",
        )
        db.add(correction)
        db.commit()

        result = list_material_issue_corrections(db=db)

        self.assertEqual(len(result), 1)
        self.assertEqual(
            set(result[0].keys()),
            {
                "correction_event_id",
                "original_issue_event_id",
                "snapshot_id",
                "work_order_no",
                "reason_code",
                "reason_note",
                "corrected_by",
                "corrected_at",
            },
        )
        self.assertEqual(result[0]["correction_event_id"], 21)

    def test_material_issue_correction_list_filters_by_work_order_no(self) -> None:
        db = self._new_db()

        db.add(
            MaterialIssueCorrectionEvent(
                correction_event_id=31,
                original_issue_event_id=20,
                snapshot_id=5,
                work_order_no="WO-MATCH",
                org_id="ORG-1",
                location_id="RM-STORE",
                reason_code="WRONG_ITEM",
                reason_note=None,
                corrected_by="auditor-a",
            )
        )
        db.add(
            MaterialIssueCorrectionEvent(
                correction_event_id=32,
                original_issue_event_id=21,
                snapshot_id=6,
                work_order_no="WO-OTHER",
                org_id="ORG-1",
                location_id="RM-STORE",
                reason_code="WRONG_QTY",
                reason_note=None,
                corrected_by="auditor-b",
            )
        )
        db.commit()

        result = list_material_issue_corrections(work_order_no="WO-MATCH", db=db)

        self.assertEqual([row["correction_event_id"] for row in result], [31])

    def test_material_issue_correction_list_filters_by_reason_code(self) -> None:
        db = self._new_db()

        db.add(
            MaterialIssueCorrectionEvent(
                correction_event_id=41,
                original_issue_event_id=30,
                snapshot_id=7,
                work_order_no="WO-REASON-1",
                org_id="ORG-1",
                location_id="RM-STORE",
                reason_code="WRONG_ITEM",
                reason_note=None,
                corrected_by="auditor-a",
            )
        )
        db.add(
            MaterialIssueCorrectionEvent(
                correction_event_id=42,
                original_issue_event_id=31,
                snapshot_id=8,
                work_order_no="WO-REASON-2",
                org_id="ORG-1",
                location_id="RM-STORE",
                reason_code="OTHER",
                reason_note="note",
                corrected_by="auditor-b",
            )
        )
        db.commit()

        result = list_material_issue_corrections(reason_code="wrong_item", db=db)

        self.assertEqual([row["correction_event_id"] for row in result], [41])

    def test_material_issue_correction_list_filters_by_corrected_by(self) -> None:
        db = self._new_db()

        db.add(
            MaterialIssueCorrectionEvent(
                correction_event_id=51,
                original_issue_event_id=40,
                snapshot_id=9,
                work_order_no="WO-BY-1",
                org_id="ORG-1",
                location_id="RM-STORE",
                reason_code="WRONG_QTY",
                reason_note=None,
                corrected_by="auditor-a",
            )
        )
        db.add(
            MaterialIssueCorrectionEvent(
                correction_event_id=52,
                original_issue_event_id=41,
                snapshot_id=10,
                work_order_no="WO-BY-2",
                org_id="ORG-1",
                location_id="RM-STORE",
                reason_code="WRONG_QTY",
                reason_note=None,
                corrected_by="auditor-b",
            )
        )
        db.commit()

        result = list_material_issue_corrections(corrected_by="auditor-b", db=db)

        self.assertEqual([row["correction_event_id"] for row in result], [52])

    def test_material_issue_correction_list_applies_limit(self) -> None:
        db = self._new_db()

        for correction_event_id in [61, 62, 63]:
            db.add(
                MaterialIssueCorrectionEvent(
                    correction_event_id=correction_event_id,
                    original_issue_event_id=correction_event_id,
                    snapshot_id=correction_event_id,
                    work_order_no=f"WO-LIMIT-{correction_event_id}",
                    org_id="ORG-1",
                    location_id="RM-STORE",
                    reason_code="WRONG_QTY",
                    reason_note=None,
                    corrected_by="auditor",
                )
            )
        db.commit()

        result = list_material_issue_corrections(limit=2, db=db)

        self.assertEqual([row["correction_event_id"] for row in result], [63, 62])

    def test_material_issue_correction_list_returns_empty_list_when_no_rows_match(self) -> None:
        db = self._new_db()

        result = list_material_issue_corrections(reason_code="WRONG_ITEM", db=db)

        self.assertEqual(result, [])

    def test_material_issue_correction_query_surfaces_share_same_field_set(self) -> None:
        db = self._new_db()

        correction = MaterialIssueCorrectionEvent(
            correction_event_id=81,
            original_issue_event_id=81,
            snapshot_id=81,
            work_order_no="WO-CORR-CONSISTENCY-1",
            org_id="ORG-1",
            location_id="RM-STORE",
            reason_code="WRONG_QTY",
            reason_note="note",
            corrected_by="auditor",
        )
        db.add(correction)
        db.commit()

        lookup_result = get_material_issue_correction(original_issue_event_id=81, db=db)
        list_result = list_material_issue_corrections(work_order_no="WO-CORR-CONSISTENCY-1", db=db)

        self.assertEqual(set(lookup_result.keys()), set(list_result[0].keys()))

    def test_material_issue_correction_query_surfaces_hide_internal_fields(self) -> None:
        db = self._new_db()

        correction = MaterialIssueCorrectionEvent(
            correction_event_id=82,
            original_issue_event_id=82,
            snapshot_id=82,
            work_order_no="WO-CORR-HIDDEN-1",
            org_id="ORG-1",
            location_id="RM-STORE",
            reason_code="WRONG_ITEM",
            reason_note=None,
            corrected_by="auditor",
        )
        db.add(correction)
        db.commit()

        lookup_result = get_material_issue_correction(original_issue_event_id=82, db=db)
        list_result = list_material_issue_corrections(work_order_no="WO-CORR-HIDDEN-1", db=db)

        for hidden_field in ["org_id", "location_id", "bom_version_id", "issue_status", "ledger_rows"]:
            self.assertNotIn(hidden_field, lookup_result)
            self.assertNotIn(hidden_field, list_result[0])

    def test_material_issue_correction_list_reason_code_normalization_is_pinned(self) -> None:
        db = self._new_db()

        db.add(
            MaterialIssueCorrectionEvent(
                correction_event_id=83,
                original_issue_event_id=83,
                snapshot_id=83,
                work_order_no="WO-CORR-NORM-1",
                org_id="ORG-1",
                location_id="RM-STORE",
                reason_code="RETURN_TO_STOCK",
                reason_note=None,
                corrected_by="auditor",
            )
        )
        db.commit()

        result = list_material_issue_corrections(reason_code="  return_to_stock  ", db=db)

        self.assertEqual([row["correction_event_id"] for row in result], [83])

    def test_material_issue_correction_list_default_ordering_is_pinned(self) -> None:
        db = self._new_db()

        for correction_event_id in [84, 85, 86]:
            db.add(
                MaterialIssueCorrectionEvent(
                    correction_event_id=correction_event_id,
                    original_issue_event_id=correction_event_id,
                    snapshot_id=correction_event_id,
                    work_order_no="WO-CORR-ORDER-1",
                    org_id="ORG-1",
                    location_id="RM-STORE",
                    reason_code="WRONG_QTY",
                    reason_note=None,
                    corrected_by="auditor",
                )
            )
        db.commit()

        result = list_material_issue_corrections(work_order_no="WO-CORR-ORDER-1", db=db)

        self.assertEqual([row["correction_event_id"] for row in result], [86, 85, 84])

    def test_material_issue_correction_query_empty_result_semantics_remain_distinct(self) -> None:
        db = self._new_db()

        with self.assertRaises(HTTPException) as exc:
            get_material_issue_correction(original_issue_event_id=999, db=db)

        list_result = list_material_issue_corrections(work_order_no="WO-NOT-FOUND", db=db)

        self.assertEqual(exc.exception.status_code, 404)
        self.assertEqual(exc.exception.detail, "Correction not found for original_issue_event_id=999")
        self.assertEqual(list_result, [])
    def test_material_issue_correction_list_is_read_only(self) -> None:
        db = self._new_db()

        snapshot = WorkOrderBOMSnapshot(
            id=2,
            work_order_no="WO-CORR-LIST-READ-ONLY-1",
            parent_system_item_code="FG-1",
            work_order_qty=1.0,
            bom_version_id=1,
            status="RELEASED",
            issue_status="ISSUED",
            created_by="test",
        )
        issue_event = MaterialIssueEvent(
            issue_event_id=2,
            snapshot_id=2,
            work_order_no="WO-CORR-LIST-READ-ONLY-1",
            bom_version_id=1,
            org_id="ORG-1",
            location_id="RM-STORE",
            issued_by="store",
        )
        correction = MaterialIssueCorrectionEvent(
            correction_event_id=71,
            original_issue_event_id=2,
            snapshot_id=2,
            work_order_no="WO-CORR-LIST-READ-ONLY-1",
            org_id="ORG-1",
            location_id="RM-STORE",
            reason_code="RETURN_TO_STOCK",
            reason_note=None,
            corrected_by="auditor",
        )
        ledger = StockLedger(
            org_id="ORG-1",
            item_id="RM-1",
            location_id="RM-STORE",
            txn_type="ISSUE",
            qty=1.0,
            uom="PCS",
            issue_event_id=2,
            snapshot_id=2,
            work_order_no="WO-CORR-LIST-READ-ONLY-1",
        )
        db.add(snapshot)
        db.add(issue_event)
        db.add(correction)
        db.add(ledger)
        db.commit()

        before_snapshot_status = db.query(WorkOrderBOMSnapshot).filter(WorkOrderBOMSnapshot.id == 2).one().issue_status
        before_issue_count = db.query(MaterialIssueEvent).count()
        before_correction_count = db.query(MaterialIssueCorrectionEvent).count()
        before_ledger_count = db.query(StockLedger).count()

        result = list_material_issue_corrections(db=db)

        self.assertEqual([row["correction_event_id"] for row in result], [71])
        self.assertEqual(db.query(MaterialIssueEvent).count(), before_issue_count)
        self.assertEqual(db.query(MaterialIssueCorrectionEvent).count(), before_correction_count)
        self.assertEqual(db.query(StockLedger).count(), before_ledger_count)
        self.assertEqual(
            db.query(WorkOrderBOMSnapshot).filter(WorkOrderBOMSnapshot.id == 2).one().issue_status,
            before_snapshot_status,
        )
    def test_material_issue_correction_rolls_back_atomically(self) -> None:
        db = self._new_db()

        root = _add_header(db, "FG-1")
        root_v = _add_version(db, root.bom_id)
        _add_line(db, root_v.version_id, sequence=10, component_code="RM-1", qty_per=2.0)

        snapshot = WorkOrderBOMSnapshot(
            work_order_no="WO-CORR-ROLLBACK-1",
            parent_system_item_code="FG-1",
            work_order_qty=3.0,
            bom_version_id=root_v.version_id,
            status="RELEASED",
            issue_status="ISSUED",
            created_by="test",
            issued_by="store",
        )
        db.add(snapshot)
        db.commit()

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

        original_ledger = StockLedger(
            org_id="ORG-1",
            item_id="RM-1",
            location_id="RM-STORE",
            txn_type="ISSUE",
            qty=6.0,
            uom="PCS",
            ref_type="WORK_ORDER_BOM_SNAPSHOT",
            ref_id=str(snapshot.id),
            note=snapshot.work_order_no,
            issue_event_id=issue_event.issue_event_id,
            snapshot_id=snapshot.id,
            work_order_no=snapshot.work_order_no,
        )
        db.add(original_ledger)
        db.commit()

        original_commit = db.commit

        def fail_commit():
            raise RuntimeError("boom")

        db.commit = fail_commit
        try:
            with self.assertRaises(HTTPException) as exc:
                work_order_material_issue_correction_commit(
                    payload=WorkOrderMaterialIssueCorrectionCommitRequest(
                        original_issue_event_id=issue_event.issue_event_id,
                        reason_code="WRONG_QTY",
                        corrected_by="auditor",
                    ),
                    db=db,
                )
        finally:
            db.commit = original_commit

        self.assertEqual(exc.exception.status_code, 500)
        self.assertEqual(
            exc.exception.detail,
            f"Material issue correction commit failed and rolled back: issue_event_id={issue_event.issue_event_id}",
        )
        self.assertEqual(db.query(MaterialIssueCorrectionEvent).count(), 0)
        ledger_rows = db.query(StockLedger).order_by(StockLedger.id.asc()).all()
        self.assertEqual(len(ledger_rows), 1)
        self.assertEqual(ledger_rows[0].txn_type, "ISSUE")
        db.refresh(snapshot)
        self.assertEqual(snapshot.issue_status, "ISSUED")

    def test_material_issue_correction_request_requires_reason_code_and_corrected_by(self) -> None:
        with self.assertRaises(ValidationError):
            WorkOrderMaterialIssueCorrectionCommitRequest(
                original_issue_event_id=1,
                corrected_by="auditor",
            )

        with self.assertRaises(ValidationError):
            WorkOrderMaterialIssueCorrectionCommitRequest(
                original_issue_event_id=1,
                reason_code="WRONG_QTY",
            )

    def test_material_issue_correction_rejects_other_without_reason_note(self) -> None:
        db = self._new_db()

        snapshot = WorkOrderBOMSnapshot(
            work_order_no="WO-CORR-OTHER-1",
            parent_system_item_code="FG-1",
            work_order_qty=1.0,
            bom_version_id=1,
            status="RELEASED",
            issue_status="ISSUED",
            created_by="test",
        )
        issue_event = MaterialIssueEvent(
            issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-OTHER-1",
            bom_version_id=1,
            org_id="ORG-1",
            location_id="RM-STORE",
            issued_by="store",
        )
        ledger = StockLedger(
            org_id="ORG-1",
            item_id="RM-1",
            location_id="RM-STORE",
            txn_type="ISSUE",
            qty=1.0,
            uom="PCS",
            issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-OTHER-1",
        )
        db.add(snapshot)
        db.add(issue_event)
        db.add(ledger)
        db.commit()

        for reason_note in [None, "   "]:
            with self.assertRaises(HTTPException) as exc:
                work_order_material_issue_correction_commit(
                    payload=WorkOrderMaterialIssueCorrectionCommitRequest(
                        original_issue_event_id=1,
                        reason_code="OTHER",
                        reason_note=reason_note,
                        corrected_by="auditor",
                    ),
                    db=db,
                )

            self.assertEqual(exc.exception.status_code, 400)
            self.assertEqual(exc.exception.detail, "reason_note is required when reason_code=OTHER")
            self.assertEqual(db.query(MaterialIssueCorrectionEvent).count(), 0)
            self.assertEqual(db.query(StockLedger).count(), 1)

    def test_material_issue_correction_revalidates_blank_reason_code_and_corrected_by(self) -> None:
        db = self._new_db()

        snapshot = WorkOrderBOMSnapshot(
            work_order_no="WO-CORR-REVALIDATE-1",
            parent_system_item_code="FG-1",
            work_order_qty=1.0,
            bom_version_id=1,
            status="RELEASED",
            issue_status="ISSUED",
            created_by="test",
        )
        issue_event = MaterialIssueEvent(
            issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-REVALIDATE-1",
            bom_version_id=1,
            org_id="ORG-1",
            location_id="RM-STORE",
            issued_by="store",
        )
        ledger = StockLedger(
            org_id="ORG-1",
            item_id="RM-1",
            location_id="RM-STORE",
            txn_type="ISSUE",
            qty=1.0,
            uom="PCS",
            issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-REVALIDATE-1",
        )
        db.add(snapshot)
        db.add(issue_event)
        db.add(ledger)
        db.commit()

        with self.assertRaises(HTTPException) as reason_exc:
            work_order_material_issue_correction_commit(
                payload=WorkOrderMaterialIssueCorrectionCommitRequest(
                    original_issue_event_id=1,
                    reason_code="   ",
                    corrected_by="auditor",
                ),
                db=db,
            )

        self.assertEqual(reason_exc.exception.status_code, 400)
        self.assertEqual(reason_exc.exception.detail, "reason_code is required")

        with self.assertRaises(HTTPException) as corrected_by_exc:
            work_order_material_issue_correction_commit(
                payload=WorkOrderMaterialIssueCorrectionCommitRequest(
                    original_issue_event_id=1,
                    reason_code="WRONG_QTY",
                    corrected_by="   ",
                ),
                db=db,
            )

        self.assertEqual(corrected_by_exc.exception.status_code, 400)
        self.assertEqual(corrected_by_exc.exception.detail, "corrected_by is required")
        self.assertEqual(db.query(MaterialIssueCorrectionEvent).count(), 0)
        self.assertEqual(db.query(StockLedger).count(), 1)
    def test_material_issue_correction_rejects_unsupported_reason_code(self) -> None:
        db = self._new_db()

        snapshot = WorkOrderBOMSnapshot(
            work_order_no="WO-CORR-BAD-1",
            parent_system_item_code="FG-1",
            work_order_qty=1.0,
            bom_version_id=1,
            status="RELEASED",
            issue_status="ISSUED",
            created_by="test",
        )
        issue_event = MaterialIssueEvent(
            issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-BAD-1",
            bom_version_id=1,
            org_id="ORG-1",
            location_id="RM-STORE",
            issued_by="store",
        )
        ledger = StockLedger(
            org_id="ORG-1",
            item_id="RM-1",
            location_id="RM-STORE",
            txn_type="ISSUE",
            qty=1.0,
            uom="PCS",
            issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-BAD-1",
        )
        db.add(snapshot)
        db.add(issue_event)
        db.add(ledger)
        db.commit()

        with self.assertRaises(HTTPException) as exc:
            work_order_material_issue_correction_commit(
                payload=WorkOrderMaterialIssueCorrectionCommitRequest(
                    original_issue_event_id=1,
                    reason_code="NOT_ALLOWED",
                    corrected_by="auditor",
                ),
                db=db,
            )

        self.assertEqual(exc.exception.status_code, 400)
        self.assertEqual(exc.exception.detail, "Unsupported correction reason_code: NOT_ALLOWED")
        self.assertEqual(db.query(MaterialIssueCorrectionEvent).count(), 0)
        self.assertEqual(db.query(StockLedger).count(), 1)

    def test_material_issue_correction_rejects_duplicate_correction_for_same_issue_event(self) -> None:
        db = self._new_db()

        snapshot = WorkOrderBOMSnapshot(
            id=1,
            work_order_no="WO-CORR-DUP-1",
            parent_system_item_code="FG-1",
            work_order_qty=1.0,
            bom_version_id=1,
            status="RELEASED",
            issue_status="ISSUED",
            created_by="test",
        )
        issue_event = MaterialIssueEvent(
            issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-DUP-1",
            bom_version_id=1,
            org_id="ORG-1",
            location_id="RM-STORE",
            issued_by="store",
        )
        correction_event = MaterialIssueCorrectionEvent(
            original_issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-DUP-1",
            org_id="ORG-1",
            location_id="RM-STORE",
            reason_code="WRONG_QTY",
            corrected_by="auditor",
        )
        ledger = StockLedger(
            org_id="ORG-1",
            item_id="RM-1",
            location_id="RM-STORE",
            txn_type="ISSUE",
            qty=1.0,
            uom="PCS",
            issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-DUP-1",
        )
        db.add(snapshot)
        db.add(issue_event)
        db.add(correction_event)
        db.add(ledger)
        db.commit()

        with self.assertRaises(HTTPException) as exc:
            work_order_material_issue_correction_commit(
                payload=WorkOrderMaterialIssueCorrectionCommitRequest(
                    original_issue_event_id=1,
                    reason_code="WRONG_QTY",
                    corrected_by="auditor-2",
                ),
                db=db,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(exc.exception.detail, "Issue event already corrected: issue_event_id=1")
        self.assertEqual(db.query(MaterialIssueCorrectionEvent).count(), 1)
        self.assertEqual(db.query(StockLedger).count(), 1)

    def test_material_issue_correction_rejects_ineligible_original_issue_trace(self) -> None:
        db = self._new_db()

        snapshot = WorkOrderBOMSnapshot(
            id=1,
            work_order_no="WO-CORR-INELIGIBLE-1",
            parent_system_item_code="FG-1",
            work_order_qty=1.0,
            bom_version_id=1,
            status="RELEASED",
            issue_status="ISSUED",
            created_by="test",
        )
        issue_event = MaterialIssueEvent(
            issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-INELIGIBLE-1",
            bom_version_id=1,
            org_id="ORG-1",
            location_id="RM-STORE",
            issued_by="store",
        )
        bad_ledger = StockLedger(
            org_id="ORG-1",
            item_id="RM-1",
            location_id="RM-STORE",
            txn_type="RECEIPT",
            qty=1.0,
            uom="PCS",
            issue_event_id=1,
            correction_event_id=99,
            snapshot_id=1,
            work_order_no="WO-CORR-INELIGIBLE-1",
        )
        db.add(snapshot)
        db.add(issue_event)
        db.add(bad_ledger)
        db.commit()

        with self.assertRaises(HTTPException) as exc:
            work_order_material_issue_correction_commit(
                payload=WorkOrderMaterialIssueCorrectionCommitRequest(
                    original_issue_event_id=1,
                    reason_code="WRONG_QTY",
                    corrected_by="auditor",
                ),
                db=db,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(exc.exception.detail, "Issue event is not eligible for correction: issue_event_id=1")
        self.assertEqual(db.query(MaterialIssueCorrectionEvent).count(), 0)
        self.assertEqual(db.query(StockLedger).count(), 1)

    def test_material_issue_correction_rejects_nonpositive_correction_qty(self) -> None:
        db = self._new_db()

        snapshot = WorkOrderBOMSnapshot(
            id=1,
            work_order_no="WO-CORR-BAD-QTY-1",
            parent_system_item_code="FG-1",
            work_order_qty=1.0,
            bom_version_id=1,
            status="RELEASED",
            issue_status="ISSUED",
            created_by="test",
        )
        issue_event = MaterialIssueEvent(
            issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-BAD-QTY-1",
            bom_version_id=1,
            org_id="ORG-1",
            location_id="RM-STORE",
            issued_by="store",
        )
        zero_qty_ledger = StockLedger(
            org_id="ORG-1",
            item_id="RM-1",
            location_id="RM-STORE",
            txn_type="ISSUE",
            qty=0.0,
            uom="PCS",
            issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-BAD-QTY-1",
        )
        db.add(snapshot)
        db.add(issue_event)
        db.add(zero_qty_ledger)
        db.commit()

        with self.assertRaises(HTTPException) as exc:
            work_order_material_issue_correction_commit(
                payload=WorkOrderMaterialIssueCorrectionCommitRequest(
                    original_issue_event_id=1,
                    reason_code="WRONG_QTY",
                    corrected_by="auditor",
                ),
                db=db,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(exc.exception.detail, "Issue event is not eligible for correction: issue_event_id=1")
        self.assertEqual(db.query(MaterialIssueCorrectionEvent).count(), 0)
        self.assertEqual(db.query(StockLedger).count(), 1)

    def test_material_issue_correction_rejects_context_mismatch_with_original_trace(self) -> None:
        db = self._new_db()

        snapshot = WorkOrderBOMSnapshot(
            id=1,
            work_order_no="WO-CORR-CONTEXT-1",
            parent_system_item_code="FG-1",
            work_order_qty=1.0,
            bom_version_id=1,
            status="RELEASED",
            issue_status="ISSUED",
            created_by="test",
        )
        issue_event = MaterialIssueEvent(
            issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-CONTEXT-1",
            bom_version_id=1,
            org_id="ORG-1",
            location_id="RM-STORE",
            issued_by="store",
        )
        mismatch_ledger = StockLedger(
            org_id="ORG-2",
            item_id="RM-1",
            location_id="RM-STORE",
            txn_type="ISSUE",
            qty=1.0,
            uom="PCS",
            issue_event_id=1,
            snapshot_id=1,
            work_order_no="WO-CORR-CONTEXT-1",
        )
        db.add(snapshot)
        db.add(issue_event)
        db.add(mismatch_ledger)
        db.commit()

        with self.assertRaises(HTTPException) as exc:
            work_order_material_issue_correction_commit(
                payload=WorkOrderMaterialIssueCorrectionCommitRequest(
                    original_issue_event_id=1,
                    reason_code="WRONG_QTY",
                    corrected_by="auditor",
                ),
                db=db,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(exc.exception.detail, "Correction context mismatch with original trace: issue_event_id=1")
        self.assertEqual(db.query(MaterialIssueCorrectionEvent).count(), 0)
        self.assertEqual(db.query(StockLedger).count(), 1)
    def test_material_issue_correction_allows_approved_reason_codes(self) -> None:
        for reason_code, reason_note in [
            ("WRONG_ITEM", None),
            ("WRONG_QTY", None),
            ("DUPLICATE_ISSUE", None),
            ("RETURN_TO_STOCK", None),
            ("OTHER", "manual explanation"),
        ]:
            db = self._new_db()

            snapshot = WorkOrderBOMSnapshot(
                work_order_no=f"WO-{reason_code}",
                parent_system_item_code="FG-1",
                work_order_qty=1.0,
                bom_version_id=1,
                status="RELEASED",
                issue_status="ISSUED",
                created_by="test",
            )
            issue_event = MaterialIssueEvent(
                issue_event_id=1,
                snapshot_id=1,
                work_order_no=f"WO-{reason_code}",
                bom_version_id=1,
                org_id="ORG-1",
                location_id="RM-STORE",
                issued_by="store",
            )
            ledger = StockLedger(
                org_id="ORG-1",
                item_id="RM-1",
                location_id="RM-STORE",
                txn_type="ISSUE",
                qty=1.0,
                uom="PCS",
                issue_event_id=1,
                snapshot_id=1,
                work_order_no=f"WO-{reason_code}",
            )
            db.add(snapshot)
            db.add(issue_event)
            db.add(ledger)
            db.commit()

            result = work_order_material_issue_correction_commit(
                payload=WorkOrderMaterialIssueCorrectionCommitRequest(
                    original_issue_event_id=1,
                    reason_code=reason_code,
                    reason_note=reason_note,
                    corrected_by="auditor",
                ),
                db=db,
            )

            self.assertEqual(result["original_issue_event_id"], 1)
            correction = db.query(MaterialIssueCorrectionEvent).one()
            self.assertEqual(correction.reason_code, reason_code)
            self.assertEqual(correction.reason_note, reason_note)
            self.assertEqual(correction.corrected_by, "auditor")


if __name__ == "__main__":
    unittest.main()
