from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_work_order_bom_snapshot_release_columns(engine: Engine) -> None:
    table_name = "work_order_bom_snapshot"
    inspector = inspect(engine)
    if not inspector.has_table(table_name):
        return

    existing_columns = {col["name"] for col in inspector.get_columns(table_name)}

    statements: list[str] = []
    if "status" not in existing_columns:
        statements.append(
            "ALTER TABLE work_order_bom_snapshot "
            "ADD COLUMN status VARCHAR DEFAULT 'DRAFT'"
        )
    if "released_by" not in existing_columns:
        statements.append(
            "ALTER TABLE work_order_bom_snapshot "
            "ADD COLUMN released_by VARCHAR"
        )
    if "released_at" not in existing_columns:
        statements.append(
            "ALTER TABLE work_order_bom_snapshot "
            "ADD COLUMN released_at DATETIME"
        )
    if "issue_status" not in existing_columns:
        statements.append(
            "ALTER TABLE work_order_bom_snapshot "
            "ADD COLUMN issue_status VARCHAR DEFAULT 'PENDING'"
        )
    if "issued_by" not in existing_columns:
        statements.append(
            "ALTER TABLE work_order_bom_snapshot "
            "ADD COLUMN issued_by VARCHAR"
        )
    if "issued_at" not in existing_columns:
        statements.append(
            "ALTER TABLE work_order_bom_snapshot "
            "ADD COLUMN issued_at DATETIME"
        )

    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))
        conn.execute(
            text(
                "UPDATE work_order_bom_snapshot "
                "SET status = 'DRAFT' "
                "WHERE status IS NULL OR TRIM(status) = ''"
            )
        )
        conn.execute(
            text(
                "UPDATE work_order_bom_snapshot "
                "SET issue_status = 'PENDING' "
                "WHERE issue_status IS NULL OR TRIM(issue_status) = ''"
            )
        )

    inspector = inspect(engine)
    detail_table_name = "work_order_bom_snapshot_line"
    if inspector.has_table(detail_table_name):
        return

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE work_order_bom_snapshot_line ("
                "id INTEGER PRIMARY KEY, "
                "snapshot_id INTEGER NOT NULL, "
                "seq_no INTEGER NOT NULL, "
                "item_code VARCHAR NOT NULL, "
                "item_name VARCHAR, "
                "required_qty FLOAT NOT NULL, "
                "uom VARCHAR NOT NULL"
                ")"
            )
        )
