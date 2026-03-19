from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_step41_anchor_control_schema(engine: Engine) -> None:
    inspector = inspect(engine)

    if inspector.has_table("work_orders"):
        existing_columns = {col["name"] for col in inspector.get_columns("work_orders")}
        if "planned_qty" not in existing_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE work_orders ADD COLUMN planned_qty FLOAT"))

    table_sql: dict[str, str] = {
        "packing_detail": (
            "CREATE TABLE packing_detail ("
            "id INTEGER PRIMARY KEY, "
            "work_order_id INTEGER NOT NULL, "
            "process_context VARCHAR NOT NULL, "
            "label_type VARCHAR NOT NULL, "
            "basis_qty FLOAT NOT NULL, "
            "pack_unit_qty FLOAT NOT NULL, "
            "full_pack_count INTEGER NOT NULL DEFAULT 0, "
            "partial_pack_qty FLOAT NOT NULL DEFAULT 0, "
            "expected_label_qty INTEGER NOT NULL DEFAULT 0, "
            "printed_label_qty INTEGER NOT NULL DEFAULT 0, "
            "remaining_printable_qty INTEGER NOT NULL DEFAULT 0, "
            "allow_partial BOOLEAN NOT NULL DEFAULT 0, "
            "created_at DATETIME NOT NULL, "
            "updated_at DATETIME NOT NULL, "
            "CONSTRAINT uq_packing_detail_scope UNIQUE (work_order_id, process_context, label_type)"
            ")"
        ),
        "expected_print_plan": (
            "CREATE TABLE expected_print_plan ("
            "id INTEGER PRIMARY KEY, "
            "work_order_id INTEGER NOT NULL, "
            "anchor_type VARCHAR NOT NULL, "
            "label_type VARCHAR NOT NULL, "
            "process_context VARCHAR NOT NULL, "
            "basis_qty FLOAT NOT NULL, "
            "expected_label_qty INTEGER NOT NULL DEFAULT 0, "
            "printed_label_qty INTEGER NOT NULL DEFAULT 0, "
            "remaining_printable_qty INTEGER NOT NULL DEFAULT 0, "
            "calculated_at DATETIME NOT NULL, "
            "CONSTRAINT uq_expected_print_plan_scope UNIQUE (work_order_id, anchor_type, label_type, process_context)"
            ")"
        ),
        "label_range_batch": (
            "CREATE TABLE label_range_batch ("
            "id INTEGER PRIMARY KEY, "
            "range_batch_id VARCHAR NOT NULL UNIQUE, "
            "work_order_id INTEGER NOT NULL, "
            "anchor_type VARCHAR NOT NULL, "
            "range_start_no INTEGER NOT NULL, "
            "range_last_no INTEGER NOT NULL, "
            "range_qty INTEGER NOT NULL, "
            "planned_qty INTEGER NOT NULL DEFAULT 0, "
            "issued_qty INTEGER NOT NULL DEFAULT 0, "
            "printed_qty INTEGER NOT NULL DEFAULT 0, "
            "issued_to_line_qty INTEGER NOT NULL DEFAULT 0, "
            "used_qty INTEGER NOT NULL DEFAULT 0, "
            "damaged_qty INTEGER NOT NULL DEFAULT 0, "
            "void_qty INTEGER NOT NULL DEFAULT 0, "
            "unused_qty INTEGER NOT NULL DEFAULT 0, "
            "issued_by VARCHAR NOT NULL, "
            "issued_at DATETIME NOT NULL, "
            "status VARCHAR NOT NULL DEFAULT 'OPEN'"
            ")"
        ),
        "label_instance": (
            "CREATE TABLE label_instance ("
            "label_instance_id INTEGER PRIMARY KEY, "
            "label_instance_uuid VARCHAR NOT NULL, "
            "anchor_type VARCHAR NOT NULL, "
            "anchor_value VARCHAR NOT NULL, "
            "work_order_id INTEGER NOT NULL, "
            "run_seq_no INTEGER NOT NULL, "
            "range_batch_id VARCHAR NOT NULL, "
            "print_status VARCHAR NOT NULL DEFAULT 'QUEUED', "
            "print_attempt_no INTEGER NOT NULL DEFAULT 0, "
            "printed_by VARCHAR, "
            "printed_at DATETIME, "
            "issued_to_line_at DATETIME, "
            "void_reason VARCHAR, "
            "reprint_reason VARCHAR, "
            "replaced_from_label_id INTEGER, "
            "CONSTRAINT uq_label_instance_uuid UNIQUE (label_instance_uuid), "
            "CONSTRAINT uq_label_instance_business_seq UNIQUE (work_order_id, anchor_type, run_seq_no)"
            ")"
        ),
        "manual_execution_entry": (
            "CREATE TABLE manual_execution_entry ("
            "id INTEGER PRIMARY KEY, "
            "anchor_type VARCHAR NOT NULL, "
            "anchor_value VARCHAR NOT NULL, "
            "process_context VARCHAR NOT NULL, "
            "qty FLOAT NOT NULL, "
            "reason_code VARCHAR NOT NULL, "
            "entered_by VARCHAR NOT NULL, "
            "approved_by VARCHAR NOT NULL, "
            "witness VARCHAR NOT NULL, "
            "override_at DATETIME NOT NULL, "
            "remark VARCHAR, "
            "status VARCHAR NOT NULL DEFAULT 'MANUAL_FALLBACK', "
            "original_manual_entry_id INTEGER, "
            "created_at DATETIME NOT NULL"
            ")"
        ),
        "fallback_session": (
            "CREATE TABLE fallback_session ("
            "id INTEGER PRIMARY KEY, "
            "line_or_station VARCHAR NOT NULL, "
            "effective_from DATETIME NOT NULL, "
            "effective_to DATETIME NOT NULL, "
            "reason_code VARCHAR NOT NULL, "
            "ordered_by VARCHAR NOT NULL, "
            "approved_by VARCHAR NOT NULL, "
            "witness VARCHAR NOT NULL, "
            "status VARCHAR NOT NULL DEFAULT 'OPEN', "
            "created_at DATETIME NOT NULL"
            ")"
        ),
        "damaged_label_record": (
            "CREATE TABLE damaged_label_record ("
            "id INTEGER PRIMARY KEY, "
            "anchor_type VARCHAR NOT NULL, "
            "anchor_value VARCHAR NOT NULL, "
            "related_work_order INTEGER NOT NULL, "
            "label_serial VARCHAR NOT NULL, "
            "damage_stage VARCHAR NOT NULL, "
            "reported_by VARCHAR NOT NULL, "
            "reported_at DATETIME NOT NULL, "
            "reason VARCHAR NOT NULL, "
            "replacement_required BOOLEAN NOT NULL DEFAULT 0"
            ")"
        ),
        "replacement_label_link": (
            "CREATE TABLE replacement_label_link ("
            "id INTEGER PRIMARY KEY, "
            "damaged_label_id INTEGER NOT NULL, "
            "replacement_label_id INTEGER NOT NULL, "
            "created_at DATETIME NOT NULL, "
            "CONSTRAINT uq_replacement_label_link_pair UNIQUE (damaged_label_id, replacement_label_id)"
            ")"
        ),
        "failure_qr_sheet_record": (
            "CREATE TABLE failure_qr_sheet_record ("
            "id INTEGER PRIMARY KEY, "
            "damaged_label_id INTEGER NOT NULL, "
            "failure_qr_sheet_no VARCHAR NOT NULL, "
            "attached_by VARCHAR NOT NULL, "
            "attached_at DATETIME NOT NULL, "
            "CONSTRAINT uq_failure_qr_sheet_pair UNIQUE (damaged_label_id, failure_qr_sheet_no)"
            ")"
        ),
    }

    with engine.begin() as conn:
        for table_name, ddl in table_sql.items():
            if not inspector.has_table(table_name):
                conn.execute(text(ddl))
