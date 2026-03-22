from __future__ import annotations

from datetime import date, datetime
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v2.daily_stock_audit import router
from app.bootstrap.step40a_daily_stock_audit_schema import ensure_step40a_daily_stock_audit_schema
from app.models_step40a_daily_stock_audit import DailyStockAuditFinding, DailyStockAuditRun, PhysicalCheckTask
from app.schemas.step40a_daily_stock_audit import (
    DailyStockAuditRiskLevel,
    DailyStockAuditRuleCode,
)
from app.services.step40a_daily_stock_audit import build_daily_stock_audit_scheduler_entry
from database import Base, get_db
from models import (
    PrebuildAuthorization,
    ScanExecutionEvent,
    ShadowBatchCase,
    StockLedger,
    WorkOrderFgReceive,
    WorkOrderRoutingSnapshotStep,
    WorkOrderShipment,
    WorkOrderWipTransfer,
)


AUDIT_DATE = date(2026, 3, 22)


def _make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    ensure_step40a_daily_stock_audit_schema(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


class Step40ADailyStockAuditTests(unittest.TestCase):
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

    def _seed_ledger_row(
        self,
        db: Session,
        *,
        org_id: str,
        item_code: str,
        stock_bucket: str,
        movement_type: str,
        txn_type: str,
        qty: float,
        posted_at: datetime,
        source_event_type: str,
        source_event_id: int,
        remark: str | None = None,
    ) -> None:
        base_qty = abs(qty)
        row = StockLedger(
            ledger_no=f"LEDGER-{org_id}-{item_code}-{source_event_id}",
            org_id=org_id,
            item_id=item_code,
            item_code=item_code,
            txn_type=txn_type,
            movement_type=movement_type,
            stock_bucket=stock_bucket,
            qty=qty,
            uom="PCS",
            txn_qty=base_qty,
            txn_uom="PCS",
            base_qty=base_qty,
            base_uom="PCS",
            source_event_type=source_event_type,
            source_event_id=source_event_id,
            posted_by="tester",
            remark=remark,
            posted_at=posted_at,
            occurred_at=posted_at,
        )
        db.add(row)
        db.flush()

    def _seed_daily_candidates(self, db: Session) -> None:
        # R01 negative balance -> physical check task
        self._seed_ledger_row(
            db,
            org_id="ORG-1",
            item_code="RM-NEG",
            stock_bucket="RAW_MATERIAL",
            movement_type="OUT",
            txn_type="ISSUE",
            qty=-5.0,
            posted_at=datetime(2026, 3, 22, 8, 0, 0),
            source_event_type="RM_ISSUE",
            source_event_id=101,
        )

        # R02 + R03 + R05 -> HIGH risk -> physical check task
        self._seed_ledger_row(
            db,
            org_id="ORG-1",
            item_code="FG-HIGH",
            stock_bucket="RAW_MATERIAL",
            movement_type="IN",
            txn_type="RECEIPT",
            qty=5.0,
            posted_at=datetime(2026, 3, 22, 9, 0, 0),
            source_event_type="FG_RECEIVE",
            source_event_id=201,
        )
        self._seed_ledger_row(
            db,
            org_id="ORG-1",
            item_code="FG-HIGH",
            stock_bucket="FINISHED_GOODS",
            movement_type="OUT",
            txn_type="ISSUE",
            qty=-2.0,
            posted_at=datetime(2026, 3, 22, 10, 0, 0),
            source_event_type="SHIPMENT",
            source_event_id=202,
        )
        self._seed_ledger_row(
            db,
            org_id="ORG-1",
            item_code="FG-HIGH",
            stock_bucket="RAW_MATERIAL",
            movement_type="IN",
            txn_type="RECEIPT",
            qty=3.0,
            posted_at=datetime(2026, 3, 22, 11, 0, 0),
            source_event_type="FG_RECEIVE",
            source_event_id=203,
        )
        self._seed_ledger_row(
            db,
            org_id="ORG-1",
            item_code="FG-HIGH",
            stock_bucket="FINISHED_GOODS",
            movement_type="OUT",
            txn_type="ISSUE",
            qty=-1.0,
            posted_at=datetime(2026, 3, 22, 12, 0, 0),
            source_event_type="SHIPMENT",
            source_event_id=204,
        )

        # R04 correction activity
        self._seed_ledger_row(
            db,
            org_id="ORG-2",
            item_code="RM-CORR",
            stock_bucket="RAW_MATERIAL",
            movement_type="IN",
            txn_type="ADJ_701",
            qty=1.0,
            posted_at=datetime(2026, 3, 22, 13, 0, 0),
            source_event_type="RM_ISSUE",
            source_event_id=301,
            remark="correction pass one",
        )
        self._seed_ledger_row(
            db,
            org_id="ORG-2",
            item_code="RM-CORR",
            stock_bucket="RAW_MATERIAL",
            movement_type="IN",
            txn_type="ADJ_702",
            qty=1.0,
            posted_at=datetime(2026, 3, 22, 14, 0, 0),
            source_event_type="RM_ISSUE",
            source_event_id=302,
            remark="correction pass two",
        )

        # different day should not be audited
        self._seed_ledger_row(
            db,
            org_id="ORG-9",
            item_code="FG-IGNORE",
            stock_bucket="FINISHED_GOODS",
            movement_type="IN",
            txn_type="RECEIPT",
            qty=5.0,
            posted_at=datetime(2026, 3, 21, 10, 0, 0),
            source_event_type="FG_RECEIVE",
            source_event_id=999,
        )
        db.commit()

    def test_manual_trigger_creates_run_findings_and_physical_check_tasks(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        self._seed_daily_candidates(db)
        before = self._forbidden_surface_snapshot(db)

        response = client.post("/v2/daily-stock-audit/runs/trigger", json={"audit_date": "2026-03-22"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": 1,
                "run_no": response.json()["run_no"],
                "audit_date": "2026-03-22",
                "trigger_source": "MANUAL",
                "scheduler_timezone": None,
                "scheduler_entry_name": None,
                "status": "SUCCESS",
                "candidate_item_count": 3,
                "finding_count": 3,
                "physical_check_task_count": 2,
                "started_at": response.json()["started_at"],
                "completed_at": response.json()["completed_at"],
            },
        )

        findings = db.query(DailyStockAuditFinding).order_by(DailyStockAuditFinding.item_code.asc()).all()
        self.assertEqual(len(findings), 3)
        self.assertEqual([finding.item_code for finding in findings], ["FG-HIGH", "RM-CORR", "RM-NEG"])
        self.assertEqual(
            findings[0].triggered_rule_codes,
            ",".join(
                [
                    DailyStockAuditRuleCode.R02_HIGH_MOVEMENT_DENSITY.value,
                    DailyStockAuditRuleCode.R03_SAME_DAY_IN_OUT_OSCILLATION.value,
                    DailyStockAuditRuleCode.R05_BUCKET_FLOW_ABNORMALITY.value,
                ]
            ),
        )
        self.assertEqual(findings[0].risk_level, DailyStockAuditRiskLevel.HIGH.value)
        self.assertEqual(findings[1].triggered_rule_codes, DailyStockAuditRuleCode.R04_EXCESSIVE_CORRECTION_ACTIVITY.value)
        self.assertEqual(findings[2].triggered_rule_codes, DailyStockAuditRuleCode.R01_NEGATIVE_BALANCE.value)

        tasks = db.query(PhysicalCheckTask).order_by(PhysicalCheckTask.item_code.asc()).all()
        self.assertEqual(len(tasks), 2)
        self.assertEqual([task.item_code for task in tasks], ["FG-HIGH", "RM-NEG"])
        self.assertEqual(before, self._forbidden_surface_snapshot(db))

    def test_duplicate_run_date_success_guard_blocks_second_run(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        self._seed_daily_candidates(db)

        first = client.post("/v2/daily-stock-audit/runs/trigger", json={"audit_date": "2026-03-22"})
        second = client.post("/v2/daily-stock-audit/runs/trigger", json={"audit_date": "2026-03-22"})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)

    def test_read_surfaces_and_filters_return_expected_contracts(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        self._seed_daily_candidates(db)
        run = client.post("/v2/daily-stock-audit/runs/trigger", json={"audit_date": "2026-03-22"}).json()

        runs = client.get("/v2/daily-stock-audit/runs", params={"trigger_source": "MANUAL"})
        high_findings = client.get("/v2/daily-stock-audit/findings", params={"risk_level": "HIGH"})
        r04_findings = client.get("/v2/daily-stock-audit/findings", params={"rule_code": "R04_EXCESSIVE_CORRECTION_ACTIVITY"})
        tasks = client.get("/v2/daily-stock-audit/physical-check-tasks", params={"run_id": run["id"], "status": "OPEN"})
        scheduler = client.get("/v2/daily-stock-audit/scheduler")

        self.assertEqual(runs.status_code, 200)
        self.assertEqual(len(runs.json()), 1)
        self.assertEqual(runs.json()[0]["audit_date"], "2026-03-22")

        self.assertEqual(high_findings.status_code, 200)
        self.assertEqual(len(high_findings.json()), 2)
        self.assertEqual({row["item_code"] for row in high_findings.json()}, {"FG-HIGH", "RM-NEG"})

        self.assertEqual(r04_findings.status_code, 200)
        self.assertEqual(len(r04_findings.json()), 1)
        self.assertEqual(r04_findings.json()[0]["item_code"], "RM-CORR")

        self.assertEqual(tasks.status_code, 200)
        self.assertEqual(len(tasks.json()), 2)
        self.assertEqual({row["item_code"] for row in tasks.json()}, {"FG-HIGH", "RM-NEG"})

        self.assertEqual(scheduler.status_code, 200)
        self.assertEqual(
            scheduler.json(),
            {
                "job_name": "daily-smart-stock-check",
                "cron": "0 0 * * *",
                "timezone": "Asia/Kuala_Lumpur",
                "enabled": True,
            },
        )

    def test_scheduler_entry_defaults_are_frozen(self) -> None:
        scheduler_entry = build_daily_stock_audit_scheduler_entry()
        self.assertEqual(scheduler_entry.job_name, "daily-smart-stock-check")
        self.assertEqual(scheduler_entry.cron, "0 0 * * *")
        self.assertEqual(scheduler_entry.timezone, "Asia/Kuala_Lumpur")
        self.assertTrue(scheduler_entry.enabled)

    def _forbidden_surface_snapshot(self, db: Session) -> dict[str, int]:
        return {
            "stock_ledger_count": db.query(StockLedger).count(),
            "wip_transfer_count": db.query(WorkOrderWipTransfer).count(),
            "fg_receive_count": db.query(WorkOrderFgReceive).count(),
            "shipment_count": db.query(WorkOrderShipment).count(),
            "routing_snapshot_step_count": db.query(WorkOrderRoutingSnapshotStep).count(),
            "prebuild_authorization_count": db.query(PrebuildAuthorization).count(),
            "shadow_case_count": db.query(ShadowBatchCase).count(),
            "scan_execution_event_count": db.query(ScanExecutionEvent).count(),
        }


if __name__ == "__main__":
    unittest.main()
