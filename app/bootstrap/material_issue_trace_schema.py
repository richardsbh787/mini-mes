from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_material_issue_trace_schema(engine: Engine) -> None:
    inspector = inspect(engine)

    with engine.begin() as conn:
        if not inspector.has_table("material_issue_event"):
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
        if not inspector.has_table("material_issue_correction_event"):
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

    inspector = inspect(engine)
    if inspector.has_table("material_issue_correction_event"):
        correction_columns = {col["name"] for col in inspector.get_columns("material_issue_correction_event")}
        correction_statements: list[str] = []
        if "reason_code" not in correction_columns:
            correction_statements.append(
                "ALTER TABLE material_issue_correction_event ADD COLUMN reason_code VARCHAR"
            )
        if "reason_note" not in correction_columns:
            correction_statements.append(
                "ALTER TABLE material_issue_correction_event ADD COLUMN reason_note VARCHAR"
            )
        with engine.begin() as conn:
            for sql in correction_statements:
                conn.execute(text(sql))
            if "reason_code" not in correction_columns:
                conn.execute(
                    text(
                        "UPDATE material_issue_correction_event "
                        "SET reason_code = 'OTHER' "
                        "WHERE reason_code IS NULL OR TRIM(reason_code) = ''"
                    )
                )

    inspector = inspect(engine)
    if not inspector.has_table("stock_ledger"):
        return

    existing_columns = {col["name"] for col in inspector.get_columns("stock_ledger")}
    statements: list[str] = []
    if "issue_event_id" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN issue_event_id INTEGER")
    if "correction_event_id" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN correction_event_id INTEGER")
    if "snapshot_id" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN snapshot_id INTEGER")
    if "work_order_no" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN work_order_no VARCHAR")

    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))
