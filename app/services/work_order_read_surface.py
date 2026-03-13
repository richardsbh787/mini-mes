from __future__ import annotations

from models import WorkOrder
from schemas import WorkOrderResponse


def build_work_order_response(work_order: WorkOrder) -> WorkOrderResponse:
    routing_definition = None
    if work_order.routing is not None:
        ordered_steps = sorted(work_order.routing.steps, key=lambda step: (step.seq_no, step.id))
        routing_definition = {
            "routing_id": work_order.routing.id,
            "routing_code": work_order.routing.routing_code,
            "routing_name": work_order.routing.routing_name,
            "routing_status": work_order.routing.status,
            "steps": [
                {
                    "seq_no": step.seq_no,
                    "step_code": step.step_code,
                    "step_name": step.step_name,
                    "department": step.department,
                    "is_required": step.is_required,
                }
                for step in ordered_steps
            ],
        }

    routing_snapshot = None
    if work_order.routing_snapshot is not None:
        ordered_snapshot_steps = sorted(
            work_order.routing_snapshot.steps,
            key=lambda step: (step.seq_no, step.id),
        )
        routing_snapshot = {
            "snapshot_id": work_order.routing_snapshot.id,
            "source_routing_id": work_order.routing_snapshot.source_routing_id,
            "routing_code": work_order.routing_snapshot.routing_code,
            "routing_name": work_order.routing_snapshot.routing_name,
            "steps": [
                {
                    "seq_no": step.seq_no,
                    "step_code": step.step_code,
                    "step_name": step.step_name,
                    "department": step.department,
                    "is_required": step.is_required,
                }
                for step in ordered_snapshot_steps
            ],
        }

    return WorkOrderResponse.model_validate(
        {
            "id": work_order.id,
            "work_order_no": work_order.work_order_no,
            "sales_order_id": work_order.sales_order_id,
            "product_id": work_order.product_id,
            "production_line_id": work_order.production_line_id,
            "routing_id": work_order.routing_id,
            "planned_hours": work_order.planned_hours,
            "actual_hours": work_order.actual_hours,
            "remaining_hours": work_order.remaining_hours,
            "priority": work_order.priority,
            "promise_date": work_order.promise_date,
            "status": work_order.status,
            "is_material_ready": work_order.is_material_ready,
            "material_ready_date": work_order.material_ready_date,
            "routing_definition": routing_definition,
            "routing_snapshot": routing_snapshot,
            "created_datetime": work_order.created_datetime,
            "started_at": work_order.started_at,
            "completed_at": work_order.completed_at,
        }
    )
