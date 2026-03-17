from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_work_order_shipment_schema(engine: Engine) -> None:
    inspector = inspect(engine)

    with engine.begin() as conn:
        if not inspector.has_table("work_order_shipment"):
            conn.execute(
                text(
                    "CREATE TABLE work_order_shipment ("
                    "id INTEGER PRIMARY KEY, "
                    "shipment_no VARCHAR NOT NULL, "
                    "work_order_id INTEGER NOT NULL, "
                    "sales_order_id INTEGER NOT NULL, "
                    "fg_receive_id INTEGER NOT NULL, "
                    "txn_qty FLOAT NOT NULL, "
                    "txn_uom VARCHAR NOT NULL, "
                    "shipment_ref VARCHAR NOT NULL, "
                    "shipment_remark VARCHAR, "
                    "shipment_status VARCHAR NOT NULL, "
                    "shipped_at DATETIME NOT NULL, "
                    "shipped_by VARCHAR NOT NULL"
                    ")"
                )
            )

    inspector = inspect(engine)
    if not inspector.has_table("work_order_shipment"):
        return

    existing_columns = {col["name"] for col in inspector.get_columns("work_order_shipment")}
    statements: list[str] = []
    if "shipment_no" not in existing_columns:
        statements.append("ALTER TABLE work_order_shipment ADD COLUMN shipment_no VARCHAR")
    if "work_order_id" not in existing_columns:
        statements.append("ALTER TABLE work_order_shipment ADD COLUMN work_order_id INTEGER")
    if "sales_order_id" not in existing_columns:
        statements.append("ALTER TABLE work_order_shipment ADD COLUMN sales_order_id INTEGER")
    if "fg_receive_id" not in existing_columns:
        statements.append("ALTER TABLE work_order_shipment ADD COLUMN fg_receive_id INTEGER")
    if "txn_qty" not in existing_columns:
        statements.append("ALTER TABLE work_order_shipment ADD COLUMN txn_qty FLOAT")
    if "txn_uom" not in existing_columns:
        statements.append("ALTER TABLE work_order_shipment ADD COLUMN txn_uom VARCHAR")
    if "shipment_ref" not in existing_columns:
        statements.append("ALTER TABLE work_order_shipment ADD COLUMN shipment_ref VARCHAR")
    if "shipment_remark" not in existing_columns:
        statements.append("ALTER TABLE work_order_shipment ADD COLUMN shipment_remark VARCHAR")
    if "shipment_status" not in existing_columns:
        statements.append("ALTER TABLE work_order_shipment ADD COLUMN shipment_status VARCHAR")
    if "shipped_at" not in existing_columns:
        statements.append("ALTER TABLE work_order_shipment ADD COLUMN shipped_at DATETIME")
    if "shipped_by" not in existing_columns:
        statements.append("ALTER TABLE work_order_shipment ADD COLUMN shipped_by VARCHAR")

    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))
