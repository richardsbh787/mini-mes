from __future__ import annotations

import os
import tempfile
import unittest

from sqlalchemy import create_engine, inspect, text

from app.bootstrap.material_issue_trace_schema import ensure_material_issue_trace_schema


class MaterialIssueTraceSchemaTests(unittest.TestCase):
    def _new_engine(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        engine = create_engine(f"sqlite:///{path}")
        self.addCleanup(engine.dispose)
        return engine

    def test_bootstrap_creates_issue_event_table_and_stock_ledger_trace_columns(self) -> None:
        engine = self._new_engine()

        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE stock_ledger ("
                    "id INTEGER PRIMARY KEY, "
                    "org_id VARCHAR NOT NULL, "
                    "item_id VARCHAR NOT NULL, "
                    "location_id VARCHAR, "
                    "txn_type VARCHAR NOT NULL, "
                    "qty FLOAT NOT NULL, "
                    "uom VARCHAR NOT NULL, "
                    "ref_type VARCHAR, "
                    "ref_id VARCHAR, "
                    "note VARCHAR, "
                    "occurred_at DATETIME NOT NULL, "
                    "created_at DATETIME NOT NULL"
                    ")"
                )
            )

        ensure_material_issue_trace_schema(engine)

        inspector = inspect(engine)
        ledger_columns = {col["name"] for col in inspector.get_columns("stock_ledger")}
        self.assertTrue(inspector.has_table("material_issue_event"))
        self.assertTrue(inspector.has_table("material_issue_correction_event"))
        self.assertTrue({"issue_event_id", "correction_event_id", "snapshot_id", "work_order_no"}.issubset(ledger_columns))
        correction_columns = {col["name"] for col in inspector.get_columns("material_issue_correction_event")}
        self.assertTrue({"reason_code", "reason_note"}.issubset(correction_columns))

    def test_bootstrap_is_idempotent_for_existing_trace_schema(self) -> None:
        engine = self._new_engine()

        with engine.begin() as conn:
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
            conn.execute(
                text(
                    "CREATE TABLE stock_ledger ("
                    "id INTEGER PRIMARY KEY, "
                    "org_id VARCHAR NOT NULL, "
                    "item_id VARCHAR NOT NULL, "
                    "location_id VARCHAR, "
                    "txn_type VARCHAR NOT NULL, "
                    "qty FLOAT NOT NULL, "
                    "uom VARCHAR NOT NULL, "
                    "ref_type VARCHAR, "
                    "ref_id VARCHAR, "
                    "note VARCHAR, "
                    "issue_event_id INTEGER, "
                    "correction_event_id INTEGER, "
                    "snapshot_id INTEGER, "
                    "work_order_no VARCHAR, "
                    "occurred_at DATETIME NOT NULL, "
                    "created_at DATETIME NOT NULL"
                    ")"
                )
            )

        ensure_material_issue_trace_schema(engine)
        ensure_material_issue_trace_schema(engine)

        inspector = inspect(engine)
        ledger_columns = {col["name"] for col in inspector.get_columns("stock_ledger")}
        self.assertTrue(inspector.has_table("material_issue_event"))
        self.assertTrue(inspector.has_table("material_issue_correction_event"))
        self.assertTrue({"issue_event_id", "correction_event_id", "snapshot_id", "work_order_no"}.issubset(ledger_columns))
        correction_columns = {col["name"] for col in inspector.get_columns("material_issue_correction_event")}
        self.assertTrue({"reason_code", "reason_note"}.issubset(correction_columns))


if __name__ == "__main__":
    unittest.main()
