from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_stock_ledger_fg_receive_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table("stock_ledger"):
        return

    existing_columns = {col["name"] for col in inspector.get_columns("stock_ledger")}
    statements: list[str] = []
    if "ledger_no" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN ledger_no VARCHAR")
    if "item_code" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN item_code VARCHAR")
    if "movement_type" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN movement_type VARCHAR")
    if "stock_bucket" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN stock_bucket VARCHAR")
    if "txn_qty" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN txn_qty FLOAT")
    if "txn_uom" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN txn_uom VARCHAR")
    if "base_qty" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN base_qty FLOAT")
    if "base_uom" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN base_uom VARCHAR")
    if "source_event_type" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN source_event_type VARCHAR")
    if "source_event_id" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN source_event_id INTEGER")
    if "work_order_id" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN work_order_id INTEGER")
    if "sales_order_id" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN sales_order_id INTEGER")
    if "posted_by" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN posted_by VARCHAR")
    if "remark" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN remark VARCHAR")
    if "posted_at" not in existing_columns:
        statements.append("ALTER TABLE stock_ledger ADD COLUMN posted_at DATETIME")

    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))
