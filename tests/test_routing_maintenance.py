from __future__ import annotations

import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from database import Base
from app.api.v2.routing_maintenance import (
    create_routing_header,
    create_routing_step,
    get_routing_header,
)
from app.schemas.routing_maintenance import RoutingHeaderCreate, RoutingStepCreate


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


class RoutingMaintenanceTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def test_create_routing_header_requires_explicit_target_identity_and_controlled_status(self) -> None:
        db = self._new_db()

        with self.assertRaises(HTTPException) as blank_item:
            create_routing_header(
                payload=RoutingHeaderCreate(
                    item_code="   ",
                    routing_code="ROUTE-100",
                    routing_name="FG Main Route",
                    status="ACTIVE",
                ),
                db=db,
            )
        self.assertEqual(blank_item.exception.status_code, 400)
        self.assertEqual(blank_item.exception.detail, "item_code is required")

        with self.assertRaises(HTTPException) as invalid_status:
            create_routing_header(
                payload=RoutingHeaderCreate(
                    item_code="FG-100",
                    routing_code="ROUTE-100",
                    routing_name="FG Main Route",
                    status="DRAFT",
                ),
                db=db,
            )
        self.assertEqual(invalid_status.exception.status_code, 400)
        self.assertEqual(invalid_status.exception.detail, "RoutingHeader.status must be ACTIVE or INACTIVE")

        row = create_routing_header(
            payload=RoutingHeaderCreate(
                item_code=" FG-100 ",
                routing_code=" ROUTE-100 ",
                routing_name=" Main Assembly ",
                status="active",
            ),
            db=db,
        )
        self.assertEqual(row.item_code, "FG-100")
        self.assertEqual(row.routing_code, "ROUTE-100")
        self.assertEqual(row.routing_name, "Main Assembly")
        self.assertEqual(row.status, "ACTIVE")

    def test_create_routing_step_requires_existing_parent_routing(self) -> None:
        db = self._new_db()

        with self.assertRaises(HTTPException) as exc:
            create_routing_step(
                routing_id=999,
                payload=RoutingStepCreate(
                    seq_no=10,
                    step_code="ASSY",
                    step_name="Assembly",
                    department="Production",
                    is_required=True,
                ),
                db=db,
            )

        self.assertEqual(exc.exception.status_code, 404)
        self.assertEqual(exc.exception.detail, "Routing header not found")

    def test_create_routing_step_enforces_unique_seq_no_within_routing_only(self) -> None:
        db = self._new_db()

        first = create_routing_header(
            payload=RoutingHeaderCreate(
                item_code="FG-100",
                routing_code="ROUTE-100",
                routing_name="Route 100",
                status="ACTIVE",
            ),
            db=db,
        )
        second = create_routing_header(
            payload=RoutingHeaderCreate(
                item_code="FG-200",
                routing_code="ROUTE-200",
                routing_name="Route 200",
                status="INACTIVE",
            ),
            db=db,
        )

        create_routing_step(
            routing_id=first.id,
            payload=RoutingStepCreate(
                seq_no=10,
                step_code="CUT",
                step_name="Cutting",
                department="Fabrication",
                is_required=True,
            ),
            db=db,
        )

        with self.assertRaises(HTTPException) as duplicate_seq:
            create_routing_step(
                routing_id=first.id,
                payload=RoutingStepCreate(
                    seq_no=10,
                    step_code="PACK",
                    step_name="Packing",
                    department="Packing",
                    is_required=False,
                ),
                db=db,
            )
        self.assertEqual(duplicate_seq.exception.status_code, 400)
        self.assertEqual(
            duplicate_seq.exception.detail,
            "RoutingStep.seq_no must be unique within the routing",
        )

        other_routing_step = create_routing_step(
            routing_id=second.id,
            payload=RoutingStepCreate(
                seq_no=10,
                step_code="PACK",
                step_name="Packing",
                department="Packing",
                is_required=True,
            ),
            db=db,
        )
        self.assertEqual(other_routing_step.seq_no, 10)

    def test_get_routing_header_returns_steps_sorted_by_seq_no(self) -> None:
        db = self._new_db()

        header = create_routing_header(
            payload=RoutingHeaderCreate(
                item_code="FG-500",
                routing_code="ROUTE-500",
                routing_name="FG Route",
                status="ACTIVE",
            ),
            db=db,
        )

        create_routing_step(
            routing_id=header.id,
            payload=RoutingStepCreate(
                seq_no=20,
                step_code="PACK",
                step_name="Packing",
                department="Packing",
                is_required=False,
            ),
            db=db,
        )
        create_routing_step(
            routing_id=header.id,
            payload=RoutingStepCreate(
                seq_no=10,
                step_code="ASSY",
                step_name="Assembly",
                department="Production",
                is_required=True,
            ),
            db=db,
        )

        detail = get_routing_header(routing_id=header.id, db=db)

        self.assertEqual(detail.item_code, "FG-500")
        self.assertEqual(detail.routing_code, "ROUTE-500")
        self.assertEqual(detail.status, "ACTIVE")
        self.assertEqual(
            [(step.seq_no, step.step_code, step.step_name, step.is_required) for step in detail.steps],
            [
                (10, "ASSY", "Assembly", True),
                (20, "PACK", "Packing", False),
            ],
        )


if __name__ == "__main__":
    unittest.main()
