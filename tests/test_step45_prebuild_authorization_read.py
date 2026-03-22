from __future__ import annotations

from datetime import date, datetime
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v2.prebuild_authorization_read import router
from app.bootstrap.step42_prebuild_authorization_schema import ensure_step42_prebuild_authorization_schema
from database import Base, get_db
from models import PrebuildAuthorization, Product, ProductionLine, SalesOrder, WorkOrder


def _make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    ensure_step42_prebuild_authorization_schema(engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


class Step45PrebuildAuthorizationReadTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def _new_client(self, db: Session) -> TestClient:
        app = FastAPI()
        app.include_router(router)

        def override_get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        self.addCleanup(client.close)
        return client

    def _seed_work_order(self, db: Session, *, suffix: str) -> WorkOrder:
        sales_order = SalesOrder(
            order_no=f"SO-45-{suffix}",
            customer_name="Customer",
            order_date=date(2026, 3, 20),
            status="OPEN",
        )
        product = Product(model_no=f"FG-45-{suffix}", model_description="FG")
        line = ProductionLine(
            line_name=f"LINE-45-{suffix}",
            working_hours_per_day=8.0,
            efficiency_rate=1.0,
            is_active=True,
        )
        db.add_all([sales_order, product, line])
        db.flush()

        work_order = WorkOrder(
            work_order_no=f"WO-45-{suffix}",
            sales_order_id=sales_order.id,
            product_id=product.id,
            production_line_id=line.id,
            planned_qty=100.0,
            planned_hours=8.0,
            actual_hours=0.0,
            remaining_hours=8.0,
            priority="NORMAL",
            promise_date=date(2026, 4, 20),
            is_material_ready=True,
            status="OPEN",
        )
        db.add(work_order)
        db.commit()
        db.refresh(work_order)
        return work_order

    def test_api_list_surface_returns_locked_contract(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order = self._seed_work_order(db, suffix="LIST")
        other_work_order = self._seed_work_order(db, suffix="LIST2")
        db.add_all(
            [
                PrebuildAuthorization(
                    prebuild_auth_no="PBA-45-LIST-1",
                    work_order_id=work_order.id,
                    authorized_qty=5.0,
                    authorized_uom="PCS",
                    reason_code="EARLY_BUILD",
                    requested_by="planner-a",
                    approved_by="manager-a",
                    approved_at=datetime(2026, 3, 20, 9, 0, 0),
                    effective_from=datetime(2026, 3, 20, 10, 0, 0),
                    status="APPROVED",
                ),
                PrebuildAuthorization(
                    prebuild_auth_no="PBA-45-LIST-2",
                    work_order_id=other_work_order.id,
                    authorized_qty=7.0,
                    authorized_uom="PCS",
                    reason_code="TRIAL",
                    requested_by="planner-b",
                    approved_by="manager-b",
                    approved_at=datetime(2026, 3, 21, 9, 0, 0),
                    effective_from=datetime(2026, 3, 21, 10, 0, 0),
                    status="VOID",
                ),
            ]
        )
        db.commit()

        response = client.get(
            "/v2/prebuild-authorizations",
            params={
                "work_order_id": work_order.id,
                "status": "APPROVED",
                "requested_by": "planner-a",
                "approved_by": "manager-a",
                "date_from": "2026-03-20",
                "date_to": "2026-03-20",
                "page": 1,
                "page_size": 20,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["page_size"], 20)
        self.assertEqual(payload["total_count"], 1)
        self.assertEqual(
            payload["items"][0],
            {
                "prebuild_auth_no": "PBA-45-LIST-1",
                "work_order_id": work_order.id,
                "authorized_qty": 5.0,
                "authorized_uom": "PCS",
                "status": "APPROVED",
                "reason_code": "EARLY_BUILD",
                "requested_by": "planner-a",
                "approved_by": "manager-a",
                "approved_at": "2026-03-20T09:00:00",
                "effective_from": "2026-03-20T10:00:00",
                "effective_to": None,
            },
        )

    def test_api_detail_surface_returns_explicit_void_fields(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        work_order = self._seed_work_order(db, suffix="DETAIL")
        row = PrebuildAuthorization(
            prebuild_auth_no="PBA-45-DETAIL-1",
            work_order_id=work_order.id,
            authorized_qty=9.0,
            authorized_uom="PCS",
            reason_code="EARLY_BUILD",
            requested_by="planner-a",
            approved_by="manager-a",
            approved_at=datetime(2026, 3, 20, 9, 0, 0),
            effective_from=datetime(2026, 3, 20, 10, 0, 0),
            status="VOID",
            remark="Read detail baseline.",
            voided_by="manager-b",
            voided_at=datetime(2026, 3, 20, 11, 30, 0),
            void_reason_code="SUPERSEDED",
            void_note="Superseded by newer approved authorization.",
            created_at=datetime(2026, 3, 20, 8, 0, 0),
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        response = client.get(
            "/v2/prebuild-authorizations/detail",
            params={"prebuild_auth_no": "PBA-45-DETAIL-1"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["id"], row.id)
        self.assertEqual(payload["prebuild_auth_no"], "PBA-45-DETAIL-1")
        self.assertEqual(payload["remark"], "Read detail baseline.")
        self.assertEqual(payload["voided_by"], "manager-b")
        self.assertEqual(payload["voided_at"], "2026-03-20T11:30:00")
        self.assertEqual(payload["void_reason_code"], "SUPERSEDED")
        self.assertEqual(payload["void_note"], "Superseded by newer approved authorization.")


if __name__ == "__main__":
    unittest.main()
