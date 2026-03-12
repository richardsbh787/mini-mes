from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_work_order_routing_binding_column(engine: Engine) -> None:
    table_name = "work_orders"
    inspector = inspect(engine)
    if not inspector.has_table(table_name):
        return

    existing_columns = {col["name"] for col in inspector.get_columns(table_name)}
    if "routing_id" in existing_columns:
        return

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE work_orders ADD COLUMN routing_id INTEGER"))
