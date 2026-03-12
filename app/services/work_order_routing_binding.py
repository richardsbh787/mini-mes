from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import Product, RoutingHeader, RoutingStep, WorkOrder


def validate_routing_binding(db: Session, product_id: int, routing_id: int) -> RoutingHeader:
    routing = db.query(RoutingHeader).filter(RoutingHeader.id == routing_id).first()
    if not routing:
        raise HTTPException(status_code=404, detail=f"Routing header not found: id={routing_id}")

    if str(routing.status).upper() != "ACTIVE":
        raise HTTPException(
            status_code=409,
            detail=f"Routing header is not ACTIVE and cannot be bound: id={routing_id}",
        )

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product not found: id={product_id}")

    product_item_code = str(product.model_no or "").strip()
    if routing.item_code != product_item_code:
        raise HTTPException(
            status_code=409,
            detail=(
                "Routing item_code does not match WorkOrder target item: "
                f"routing_id={routing_id}, routing_item_code={routing.item_code}, "
                f"work_order_item_code={product_item_code}"
            ),
        )

    steps = (
        db.query(RoutingStep)
        .filter(RoutingStep.routing_id == routing_id)
        .order_by(RoutingStep.seq_no.asc(), RoutingStep.id.asc())
        .all()
    )
    if not steps:
        raise HTTPException(
            status_code=409,
            detail=f"Routing header has no steps and cannot be bound: id={routing_id}",
        )

    seq_nos = [step.seq_no for step in steps]
    if any(seq_no <= 0 for seq_no in seq_nos):
        raise HTTPException(
            status_code=409,
            detail=f"Routing header has invalid non-positive seq_no and cannot be bound: id={routing_id}",
        )
    if len(set(seq_nos)) != len(seq_nos):
        raise HTTPException(
            status_code=409,
            detail=f"Routing header has duplicate seq_no values and cannot be bound: id={routing_id}",
        )

    return routing


def bind_work_order_to_routing(db: Session, work_order: WorkOrder, routing_id: int) -> WorkOrder:
    validate_routing_binding(db=db, product_id=work_order.product_id, routing_id=routing_id)
    work_order.routing_id = routing_id
    db.add(work_order)
    db.commit()
    db.refresh(work_order)
    return work_order
