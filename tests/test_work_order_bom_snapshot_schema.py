from __future__ import annotations

import os
import tempfile
import unittest

from sqlalchemy import create_engine, inspect, text

from app.bootstrap.work_order_bom_snapshot_schema import ensure_work_order_bom_snapshot_release_columns


class WorkOrderBOMSnapshotSchemaTests(unittest.TestCase):
    def _new_engine(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        engine = create_engine(f"sqlite:///{path}")
        self.addCleanup(engine.dispose)
        return engine

    def test_bootstrap_adds_missing_columns_and_backfills_defaults(self) -> None:
        engine = self._new_engine()

        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE work_order_bom_snapshot ("
                    "id INTEGER PRIMARY KEY, "
                    "work_order_no VARCHAR NOT NULL, "
                    "parent_system_item_code VARCHAR NOT NULL, "
                    "work_order_qty FLOAT NOT NULL, "
                    "bom_version_id INTEGER NOT NULL"
                    ")"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO work_order_bom_snapshot "
                    "(id, work_order_no, parent_system_item_code, work_order_qty, bom_version_id) "
                    "VALUES (1, 'WO-1', 'FG-1', 3.0, 101)"
                )
            )

        ensure_work_order_bom_snapshot_release_columns(engine)

        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("work_order_bom_snapshot")}
        self.assertEqual(
            columns,
            {
                "id",
                "work_order_no",
                "parent_system_item_code",
                "work_order_qty",
                "bom_version_id",
                "status",
                "released_by",
                "released_at",
                "issue_status",
                "issued_by",
                "issued_at",
            },
        )

        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT status, issue_status, released_by, released_at, issued_by, issued_at "
                    "FROM work_order_bom_snapshot WHERE id = 1"
                )
            ).mappings().one()

        self.assertEqual(row["status"], "DRAFT")
        self.assertEqual(row["issue_status"], "PENDING")
        self.assertIsNone(row["released_by"])
        self.assertIsNone(row["released_at"])
        self.assertIsNone(row["issued_by"])
        self.assertIsNone(row["issued_at"])

    def test_bootstrap_is_idempotent_and_normalizes_blank_status_fields(self) -> None:
        engine = self._new_engine()

        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE work_order_bom_snapshot ("
                    "id INTEGER PRIMARY KEY, "
                    "work_order_no VARCHAR NOT NULL, "
                    "parent_system_item_code VARCHAR NOT NULL, "
                    "work_order_qty FLOAT NOT NULL, "
                    "bom_version_id INTEGER NOT NULL, "
                    "status VARCHAR, "
                    "released_by VARCHAR, "
                    "released_at DATETIME, "
                    "issue_status VARCHAR, "
                    "issued_by VARCHAR, "
                    "issued_at DATETIME"
                    ")"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO work_order_bom_snapshot "
                    "(id, work_order_no, parent_system_item_code, work_order_qty, bom_version_id, status, issue_status) "
                    "VALUES (1, 'WO-1', 'FG-1', 3.0, 101, '', '')"
                )
            )

        ensure_work_order_bom_snapshot_release_columns(engine)
        ensure_work_order_bom_snapshot_release_columns(engine)

        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT status, issue_status FROM work_order_bom_snapshot WHERE id = 1"
                )
            ).mappings().one()

        self.assertEqual(row["status"], "DRAFT")
        self.assertEqual(row["issue_status"], "PENDING")


if __name__ == "__main__":
    unittest.main()
