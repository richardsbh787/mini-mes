from __future__ import annotations

from types import SimpleNamespace
import unittest

from fastapi import HTTPException

from app.services.work_order_routing_readiness import validate_work_order_execution_ready_snapshot


def _make_step(
    *,
    step_id: int,
    seq_no: int | None,
    step_code: str | None,
    step_name: str | None,
    is_required: bool | None,
    department: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=step_id,
        seq_no=seq_no,
        step_code=step_code,
        step_name=step_name,
        department=department,
        is_required=is_required,
    )


def _make_snapshot(
    *,
    snapshot_id: int = 101,
    work_order_id: int = 201,
    source_routing_id: int = 301,
    routing_code: str | None = "R-READY-1",
    routing_name: str | None = "Routing READY-1",
    steps: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=snapshot_id,
        work_order_id=work_order_id,
        source_routing_id=source_routing_id,
        routing_code=routing_code,
        routing_name=routing_name,
        steps=[] if steps is None else steps,
    )


class WorkOrderRoutingReadinessTests(unittest.TestCase):
    def test_valid_snapshot_passes_readiness_and_orders_steps_by_seq_no_then_id(self) -> None:
        ready_snapshot = validate_work_order_execution_ready_snapshot(
            _make_snapshot(
                steps=[
                    _make_step(step_id=22, seq_no=20, step_code="PACK", step_name="Packing", is_required=False),
                    _make_step(step_id=11, seq_no=10, step_code="ASSY", step_name="Assembly", is_required=True),
                ]
            ),
            work_order_id=201,
        )

        self.assertEqual(ready_snapshot.snapshot_id, 101)
        self.assertEqual(
            [(step.seq_no, step.id, step.step_code, step.step_name, step.is_required) for step in ready_snapshot.steps],
            [
                (10, 11, "ASSY", "Assembly", True),
                (20, 22, "PACK", "Packing", False),
            ],
        )

    def test_missing_snapshot_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            validate_work_order_execution_ready_snapshot(None, work_order_id=201)

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder has no routing snapshot and cannot resolve execution routing authority: id=201",
        )

    def test_empty_step_snapshot_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            validate_work_order_execution_ready_snapshot(_make_snapshot(steps=[]), work_order_id=201)

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder routing snapshot is not execution-ready: snapshot has no steps: snapshot_id=101",
        )

    def test_duplicate_seq_no_snapshot_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            validate_work_order_execution_ready_snapshot(
                _make_snapshot(
                    steps=[
                        _make_step(step_id=11, seq_no=10, step_code="ASSY", step_name="Assembly", is_required=True),
                        _make_step(step_id=22, seq_no=10, step_code="PACK", step_name="Packing", is_required=False),
                    ]
                ),
                work_order_id=201,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder routing snapshot is not execution-ready: duplicate seq_no=10 in snapshot_id=101",
        )

    def test_missing_step_code_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            validate_work_order_execution_ready_snapshot(
                _make_snapshot(
                    steps=[_make_step(step_id=11, seq_no=10, step_code=None, step_name="Assembly", is_required=True)]
                ),
                work_order_id=201,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder routing snapshot is not execution-ready: snapshot step missing step_code: snapshot_id=101, step_id=11",
        )

    def test_missing_step_name_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            validate_work_order_execution_ready_snapshot(
                _make_snapshot(
                    steps=[_make_step(step_id=11, seq_no=10, step_code="ASSY", step_name=None, is_required=True)]
                ),
                work_order_id=201,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder routing snapshot is not execution-ready: snapshot step missing step_name: snapshot_id=101, step_id=11",
        )

    def test_missing_is_required_is_rejected(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            validate_work_order_execution_ready_snapshot(
                _make_snapshot(
                    steps=[_make_step(step_id=11, seq_no=10, step_code="ASSY", step_name="Assembly", is_required=None)]
                ),
                work_order_id=201,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder routing snapshot is not execution-ready: snapshot step missing is_required: snapshot_id=101, step_id=11",
        )

    def test_missing_seq_no_is_rejected_before_sorting_steps(self) -> None:
        with self.assertRaises(HTTPException) as exc:
            validate_work_order_execution_ready_snapshot(
                _make_snapshot(
                    steps=[
                        _make_step(step_id=11, seq_no=None, step_code="ASSY", step_name="Assembly", is_required=True),
                        _make_step(step_id=22, seq_no=10, step_code="PACK", step_name="Packing", is_required=False),
                    ]
                ),
                work_order_id=201,
            )

        self.assertEqual(exc.exception.status_code, 409)
        self.assertEqual(
            exc.exception.detail,
            "WorkOrder routing snapshot is not execution-ready: snapshot step missing seq_no: snapshot_id=101, step_id=11",
        )


if __name__ == "__main__":
    unittest.main()
