from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_work_order_routing_execution_state_columns(engine: Engine) -> None:
    table_name = "work_order_routing_snapshot_step"
    inspector = inspect(engine)
    if not inspector.has_table(table_name):
        return

    existing_columns = {col["name"] for col in inspector.get_columns(table_name)}

    with engine.begin() as conn:
        if "execution_status" not in existing_columns:
            conn.execute(text("ALTER TABLE work_order_routing_snapshot_step ADD COLUMN execution_status VARCHAR(32)"))
        if "started_at" not in existing_columns:
            conn.execute(text("ALTER TABLE work_order_routing_snapshot_step ADD COLUMN started_at DATETIME"))
        if "started_by" not in existing_columns:
            conn.execute(text("ALTER TABLE work_order_routing_snapshot_step ADD COLUMN started_by VARCHAR"))
        if "completed_at" not in existing_columns:
            conn.execute(text("ALTER TABLE work_order_routing_snapshot_step ADD COLUMN completed_at DATETIME"))
        if "completed_by" not in existing_columns:
            conn.execute(text("ALTER TABLE work_order_routing_snapshot_step ADD COLUMN completed_by VARCHAR"))

        conn.execute(
            text(
                "UPDATE work_order_routing_snapshot_step "
                "SET execution_status = 'PENDING' "
                "WHERE execution_status IS NULL OR TRIM(execution_status) = ''"
            )
        )
