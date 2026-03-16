from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_work_order_wip_transfer_schema(engine: Engine) -> None:
    inspector = inspect(engine)

    with engine.begin() as conn:
        if not inspector.has_table("work_order_wip_transfer"):
            conn.execute(
                text(
                    "CREATE TABLE work_order_wip_transfer ("
                    "id INTEGER PRIMARY KEY, "
                    "transfer_no VARCHAR NOT NULL, "
                    "work_order_id INTEGER NOT NULL, "
                    "routing_snapshot_id INTEGER NOT NULL, "
                    "from_step_no INTEGER NOT NULL, "
                    "to_step_no INTEGER NOT NULL, "
                    "handling_unit_type VARCHAR NOT NULL, "
                    "handling_unit_label VARCHAR, "
                    "txn_qty FLOAT NOT NULL, "
                    "txn_uom VARCHAR NOT NULL, "
                    "base_qty FLOAT NOT NULL, "
                    "base_uom VARCHAR NOT NULL, "
                    "transfer_status VARCHAR NOT NULL, "
                    "created_at DATETIME NOT NULL, "
                    "created_by VARCHAR NOT NULL"
                    ")"
                )
            )

    inspector = inspect(engine)
    if not inspector.has_table("work_order_wip_transfer"):
        return

    existing_columns = {col["name"] for col in inspector.get_columns("work_order_wip_transfer")}
    statements: list[str] = []
    if "transfer_no" not in existing_columns:
        statements.append("ALTER TABLE work_order_wip_transfer ADD COLUMN transfer_no VARCHAR")
    if "work_order_id" not in existing_columns:
        statements.append("ALTER TABLE work_order_wip_transfer ADD COLUMN work_order_id INTEGER")
    if "routing_snapshot_id" not in existing_columns:
        statements.append("ALTER TABLE work_order_wip_transfer ADD COLUMN routing_snapshot_id INTEGER")
    if "from_step_no" not in existing_columns:
        statements.append("ALTER TABLE work_order_wip_transfer ADD COLUMN from_step_no INTEGER")
    if "to_step_no" not in existing_columns:
        statements.append("ALTER TABLE work_order_wip_transfer ADD COLUMN to_step_no INTEGER")
    if "handling_unit_type" not in existing_columns:
        statements.append("ALTER TABLE work_order_wip_transfer ADD COLUMN handling_unit_type VARCHAR")
    if "handling_unit_label" not in existing_columns:
        statements.append("ALTER TABLE work_order_wip_transfer ADD COLUMN handling_unit_label VARCHAR")
    if "txn_qty" not in existing_columns:
        statements.append("ALTER TABLE work_order_wip_transfer ADD COLUMN txn_qty FLOAT")
    if "txn_uom" not in existing_columns:
        statements.append("ALTER TABLE work_order_wip_transfer ADD COLUMN txn_uom VARCHAR")
    if "base_qty" not in existing_columns:
        statements.append("ALTER TABLE work_order_wip_transfer ADD COLUMN base_qty FLOAT")
    if "base_uom" not in existing_columns:
        statements.append("ALTER TABLE work_order_wip_transfer ADD COLUMN base_uom VARCHAR")
    if "transfer_status" not in existing_columns:
        statements.append("ALTER TABLE work_order_wip_transfer ADD COLUMN transfer_status VARCHAR")
    if "created_at" not in existing_columns:
        statements.append("ALTER TABLE work_order_wip_transfer ADD COLUMN created_at DATETIME")
    if "created_by" not in existing_columns:
        statements.append("ALTER TABLE work_order_wip_transfer ADD COLUMN created_by VARCHAR")

    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))
