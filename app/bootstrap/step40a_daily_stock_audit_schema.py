from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_step40a_daily_stock_audit_schema(engine: Engine) -> None:
    inspector = inspect(engine)

    with engine.begin() as conn:
        if not inspector.has_table("daily_stock_audit_run"):
            conn.execute(
                text(
                    "CREATE TABLE daily_stock_audit_run ("
                    "id INTEGER PRIMARY KEY, "
                    "run_no VARCHAR NOT NULL UNIQUE, "
                    "audit_date DATE NOT NULL, "
                    "trigger_source VARCHAR NOT NULL, "
                    "scheduler_timezone VARCHAR, "
                    "scheduler_entry_name VARCHAR, "
                    "status VARCHAR NOT NULL, "
                    "candidate_item_count INTEGER NOT NULL DEFAULT 0, "
                    "finding_count INTEGER NOT NULL DEFAULT 0, "
                    "physical_check_task_count INTEGER NOT NULL DEFAULT 0, "
                    "started_at DATETIME NOT NULL, "
                    "completed_at DATETIME NOT NULL"
                    ")"
                )
            )
        if not inspector.has_table("daily_stock_audit_finding"):
            conn.execute(
                text(
                    "CREATE TABLE daily_stock_audit_finding ("
                    "id INTEGER PRIMARY KEY, "
                    "run_id INTEGER NOT NULL, "
                    "org_id VARCHAR NOT NULL, "
                    "item_id VARCHAR, "
                    "item_code VARCHAR NOT NULL, "
                    "primary_stock_bucket VARCHAR, "
                    "audit_date DATE NOT NULL, "
                    "triggered_rule_codes VARCHAR NOT NULL, "
                    "risk_score INTEGER NOT NULL DEFAULT 0, "
                    "risk_level VARCHAR NOT NULL, "
                    "movement_count INTEGER NOT NULL DEFAULT 0, "
                    "correction_count INTEGER NOT NULL DEFAULT 0, "
                    "net_balance_qty FLOAT NOT NULL DEFAULT 0, "
                    "distinct_bucket_count INTEGER NOT NULL DEFAULT 0, "
                    "suspicious_summary VARCHAR NOT NULL, "
                    "created_at DATETIME NOT NULL"
                    ")"
                )
            )
        if not inspector.has_table("physical_check_task"):
            conn.execute(
                text(
                    "CREATE TABLE physical_check_task ("
                    "id INTEGER PRIMARY KEY, "
                    "task_no VARCHAR NOT NULL UNIQUE, "
                    "run_id INTEGER NOT NULL, "
                    "finding_id INTEGER NOT NULL, "
                    "org_id VARCHAR NOT NULL, "
                    "item_code VARCHAR NOT NULL, "
                    "status VARCHAR NOT NULL DEFAULT 'OPEN', "
                    "priority VARCHAR NOT NULL DEFAULT 'HIGH', "
                    "reason_code VARCHAR NOT NULL, "
                    "created_at DATETIME NOT NULL"
                    ")"
                )
            )
