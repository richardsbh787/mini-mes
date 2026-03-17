from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_work_order_fg_receive_schema(engine: Engine) -> None:
    inspector = inspect(engine)

    with engine.begin() as conn:
        if not inspector.has_table("work_order_fg_receive"):
            conn.execute(
                text(
                    "CREATE TABLE work_order_fg_receive ("
                    "id INTEGER PRIMARY KEY, "
                    "fg_receive_no VARCHAR NOT NULL, "
                    "work_order_id INTEGER NOT NULL, "
                    "wip_transfer_id INTEGER NOT NULL, "
                    "routing_snapshot_id INTEGER NOT NULL, "
                    "fg_handling_unit_type VARCHAR NOT NULL, "
                    "fg_handling_unit_label VARCHAR, "
                    "txn_qty FLOAT NOT NULL, "
                    "txn_uom VARCHAR NOT NULL, "
                    "receive_status VARCHAR NOT NULL, "
                    "received_at DATETIME NOT NULL, "
                    "received_by VARCHAR NOT NULL, "
                    "remark VARCHAR"
                    ")"
                )
            )

    inspector = inspect(engine)
    if not inspector.has_table("work_order_fg_receive"):
        return

    existing_columns = {col["name"] for col in inspector.get_columns("work_order_fg_receive")}
    statements: list[str] = []
    if "fg_receive_no" not in existing_columns:
        statements.append("ALTER TABLE work_order_fg_receive ADD COLUMN fg_receive_no VARCHAR")
    if "work_order_id" not in existing_columns:
        statements.append("ALTER TABLE work_order_fg_receive ADD COLUMN work_order_id INTEGER")
    if "wip_transfer_id" not in existing_columns:
        statements.append("ALTER TABLE work_order_fg_receive ADD COLUMN wip_transfer_id INTEGER")
    if "routing_snapshot_id" not in existing_columns:
        statements.append("ALTER TABLE work_order_fg_receive ADD COLUMN routing_snapshot_id INTEGER")
    if "fg_handling_unit_type" not in existing_columns:
        statements.append("ALTER TABLE work_order_fg_receive ADD COLUMN fg_handling_unit_type VARCHAR")
    if "fg_handling_unit_label" not in existing_columns:
        statements.append("ALTER TABLE work_order_fg_receive ADD COLUMN fg_handling_unit_label VARCHAR")
    if "txn_qty" not in existing_columns:
        statements.append("ALTER TABLE work_order_fg_receive ADD COLUMN txn_qty FLOAT")
    if "txn_uom" not in existing_columns:
        statements.append("ALTER TABLE work_order_fg_receive ADD COLUMN txn_uom VARCHAR")
    if "receive_status" not in existing_columns:
        statements.append("ALTER TABLE work_order_fg_receive ADD COLUMN receive_status VARCHAR")
    if "received_at" not in existing_columns:
        statements.append("ALTER TABLE work_order_fg_receive ADD COLUMN received_at DATETIME")
    if "received_by" not in existing_columns:
        statements.append("ALTER TABLE work_order_fg_receive ADD COLUMN received_by VARCHAR")
    if "remark" not in existing_columns:
        statements.append("ALTER TABLE work_order_fg_receive ADD COLUMN remark VARCHAR")

    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))
