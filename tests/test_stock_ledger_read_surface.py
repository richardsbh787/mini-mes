from __future__ import annotations

from datetime import datetime
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v2.stock_ledger_read import router
from database import Base, get_db
from models import StockLedger


def _make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


class StockLedgerReadSurfaceTests(unittest.TestCase):
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

    def _seed_ledger(
        self,
        db: Session,
        *,
        org_id: str = "ORG-READ",
        item_code: str,
        stock_bucket: str,
        movement_type: str,
        txn_type: str,
        qty: float,
        base_qty: float,
        base_uom: str,
        source_event_type: str,
        source_event_id: int,
        source_event_line_id: int | None = None,
        posted_at: datetime | None = None,
        posted_by: str = "reader",
        remark: str | None = None,
    ) -> StockLedger:
        normalized_posted_at = posted_at or datetime(2026, 3, 18, 8, 0, 0)
        row = StockLedger(
            org_id=org_id,
            ledger_no=f"SLED-{item_code}-{source_event_type}-{source_event_id}",
            item_id=item_code,
            item_code=item_code,
            txn_type=txn_type,
            movement_type=movement_type,
            stock_bucket=stock_bucket,
            qty=qty,
            uom=base_uom,
            txn_qty=abs(qty),
            txn_uom=base_uom,
            base_qty=base_qty,
            base_uom=base_uom,
            source_event_type=source_event_type,
            source_event_id=source_event_id,
            source_event_line_id=source_event_line_id,
            posted_by=posted_by,
            posted_at=normalized_posted_at,
            occurred_at=normalized_posted_at,
            remark=remark,
        )
        db.add(row)
        db.flush()
        return row

    def test_balance_returns_correct_contract_and_supports_required_filters(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        self._seed_ledger(
            db,
            item_code="FG-100",
            stock_bucket="FINISHED_GOODS",
            movement_type="IN",
            txn_type="RECEIPT",
            qty=10.0,
            base_qty=10.0,
            base_uom="PCS",
            source_event_type="FG_RECEIVE",
            source_event_id=101,
            posted_at=datetime(2026, 3, 17, 9, 0, 0),
        )
        self._seed_ledger(
            db,
            item_code="FG-100",
            stock_bucket="FINISHED_GOODS",
            movement_type="OUT",
            txn_type="ISSUE",
            qty=-4.0,
            base_qty=4.0,
            base_uom="PCS",
            source_event_type="SHIPMENT",
            source_event_id=102,
            posted_at=datetime(2026, 3, 18, 14, 30, 0),
        )
        self._seed_ledger(
            db,
            item_code="FG-200",
            stock_bucket="FINISHED_GOODS",
            movement_type="IN",
            txn_type="RECEIPT",
            qty=6.0,
            base_qty=6.0,
            base_uom="PCS",
            source_event_type="FG_RECEIVE",
            source_event_id=103,
            posted_at=datetime(2026, 3, 16, 12, 0, 0),
        )
        self._seed_ledger(
            db,
            item_code="RM-200",
            stock_bucket="RAW_MATERIAL",
            movement_type="OUT",
            txn_type="ISSUE",
            qty=-3.0,
            base_qty=3.0,
            base_uom="KG",
            source_event_type="RM_ISSUE",
            source_event_id=104,
            source_event_line_id=9001,
            posted_at=datetime(2026, 3, 18, 7, 0, 0),
        )
        db.commit()

        all_rows = client.get("/v2/stock-ledger/balance", params={"org_id": "ORG-READ"})
        self.assertEqual(all_rows.status_code, 200)
        self.assertEqual(
            all_rows.json(),
            [
                {
                    "item_code": "FG-100",
                    "stock_bucket": "FINISHED_GOODS",
                    "base_uom": "PCS",
                    "total_in_qty": 10.0,
                    "total_out_qty": 4.0,
                    "net_balance_qty": 6.0,
                    "last_posted_at": "2026-03-18T14:30:00",
                },
                {
                    "item_code": "FG-200",
                    "stock_bucket": "FINISHED_GOODS",
                    "base_uom": "PCS",
                    "total_in_qty": 6.0,
                    "total_out_qty": 0.0,
                    "net_balance_qty": 6.0,
                    "last_posted_at": "2026-03-16T12:00:00",
                },
                {
                    "item_code": "RM-200",
                    "stock_bucket": "RAW_MATERIAL",
                    "base_uom": "KG",
                    "total_in_qty": 0.0,
                    "total_out_qty": 3.0,
                    "net_balance_qty": -3.0,
                    "last_posted_at": "2026-03-18T07:00:00",
                },
            ],
        )

        item_filtered = client.get(
            "/v2/stock-ledger/balance",
            params={"org_id": "ORG-READ", "item_code": "FG-100"},
        )
        bucket_filtered = client.get(
            "/v2/stock-ledger/balance",
            params={"org_id": "ORG-READ", "stock_bucket": "RAW_MATERIAL"},
        )
        event_filtered = client.get(
            "/v2/stock-ledger/balance",
            params={"org_id": "ORG-READ", "source_event_type": "SHIPMENT"},
        )
        date_filtered = client.get(
            "/v2/stock-ledger/balance",
            params={
                "org_id": "ORG-READ",
                "date_from": "2026-03-18",
                "date_to": "2026-03-18",
            },
        )

        self.assertEqual(item_filtered.status_code, 200)
        self.assertEqual(len(item_filtered.json()), 1)
        self.assertEqual(item_filtered.json()[0]["item_code"], "FG-100")

        self.assertEqual(bucket_filtered.status_code, 200)
        self.assertEqual(bucket_filtered.json(), [
            {
                "item_code": "RM-200",
                "stock_bucket": "RAW_MATERIAL",
                "base_uom": "KG",
                "total_in_qty": 0.0,
                "total_out_qty": 3.0,
                "net_balance_qty": -3.0,
                "last_posted_at": "2026-03-18T07:00:00",
            }
        ])

        self.assertEqual(event_filtered.status_code, 200)
        self.assertEqual(event_filtered.json(), [
            {
                "item_code": "FG-100",
                "stock_bucket": "FINISHED_GOODS",
                "base_uom": "PCS",
                "total_in_qty": 0.0,
                "total_out_qty": 4.0,
                "net_balance_qty": -4.0,
                "last_posted_at": "2026-03-18T14:30:00",
            }
        ])

        self.assertEqual(date_filtered.status_code, 200)
        self.assertEqual(
            date_filtered.json(),
            [
                {
                    "item_code": "FG-100",
                    "stock_bucket": "FINISHED_GOODS",
                    "base_uom": "PCS",
                    "total_in_qty": 0.0,
                    "total_out_qty": 4.0,
                    "net_balance_qty": -4.0,
                    "last_posted_at": "2026-03-18T14:30:00",
                },
                {
                    "item_code": "RM-200",
                    "stock_bucket": "RAW_MATERIAL",
                    "base_uom": "KG",
                    "total_in_qty": 0.0,
                    "total_out_qty": 3.0,
                    "net_balance_qty": -3.0,
                    "last_posted_at": "2026-03-18T07:00:00",
                },
            ],
        )

    def test_entries_support_all_required_filters_and_pagination(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        self._seed_ledger(
            db,
            item_code="FG-300",
            stock_bucket="FINISHED_GOODS",
            movement_type="IN",
            txn_type="RECEIPT",
            qty=5.0,
            base_qty=5.0,
            base_uom="PCS",
            source_event_type="FG_RECEIVE",
            source_event_id=301,
            posted_at=datetime(2026, 3, 16, 8, 0, 0),
        )
        self._seed_ledger(
            db,
            item_code="FG-300",
            stock_bucket="FINISHED_GOODS",
            movement_type="OUT",
            txn_type="ISSUE",
            qty=-2.0,
            base_qty=2.0,
            base_uom="PCS",
            source_event_type="SHIPMENT",
            source_event_id=302,
            posted_at=datetime(2026, 3, 17, 8, 0, 0),
        )
        self._seed_ledger(
            db,
            item_code="RM-300",
            stock_bucket="RAW_MATERIAL",
            movement_type="OUT",
            txn_type="ISSUE",
            qty=-1.5,
            base_qty=1.5,
            base_uom="KG",
            source_event_type="RM_ISSUE",
            source_event_id=303,
            source_event_line_id=3303,
            posted_at=datetime(2026, 3, 18, 8, 0, 0),
        )
        db.commit()

        first_page = client.get(
            "/v2/stock-ledger/entries",
            params={"org_id": "ORG-READ", "page": 1, "page_size": 2},
        )
        second_page = client.get(
            "/v2/stock-ledger/entries",
            params={"org_id": "ORG-READ", "page": 2, "page_size": 2},
        )
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(len(first_page.json()), 2)
        self.assertEqual(
            [row["source_event_type"] for row in first_page.json()],
            ["RM_ISSUE", "SHIPMENT"],
        )
        self.assertEqual(first_page.json()[1]["source_event_line_id"], None)

        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(len(second_page.json()), 1)
        self.assertEqual(second_page.json()[0]["source_event_type"], "FG_RECEIVE")
        self.assertEqual(second_page.json()[0]["source_event_line_id"], None)

        item_filtered = client.get(
            "/v2/stock-ledger/entries",
            params={"org_id": "ORG-READ", "item_code": "FG-300"},
        )
        bucket_filtered = client.get(
            "/v2/stock-ledger/entries",
            params={"org_id": "ORG-READ", "stock_bucket": "RAW_MATERIAL"},
        )
        movement_filtered = client.get(
            "/v2/stock-ledger/entries",
            params={"org_id": "ORG-READ", "movement_type": "OUT"},
        )
        type_filtered = client.get(
            "/v2/stock-ledger/entries",
            params={"org_id": "ORG-READ", "source_event_type": "SHIPMENT"},
        )
        event_id_filtered = client.get(
            "/v2/stock-ledger/entries",
            params={"org_id": "ORG-READ", "source_event_id": 303},
        )
        date_filtered = client.get(
            "/v2/stock-ledger/entries",
            params={
                "org_id": "ORG-READ",
                "date_from": "2026-03-17",
                "date_to": "2026-03-18",
            },
        )

        self.assertEqual(item_filtered.status_code, 200)
        self.assertEqual([row["source_event_type"] for row in item_filtered.json()], ["SHIPMENT", "FG_RECEIVE"])

        self.assertEqual(bucket_filtered.status_code, 200)
        self.assertEqual(len(bucket_filtered.json()), 1)
        self.assertEqual(bucket_filtered.json()[0]["item_code"], "RM-300")
        self.assertEqual(bucket_filtered.json()[0]["source_event_line_id"], 3303)

        self.assertEqual(movement_filtered.status_code, 200)
        self.assertEqual([row["movement_type"] for row in movement_filtered.json()], ["OUT", "OUT"])

        self.assertEqual(type_filtered.status_code, 200)
        self.assertEqual(len(type_filtered.json()), 1)
        self.assertEqual(type_filtered.json()[0]["source_event_id"], 302)

        self.assertEqual(event_id_filtered.status_code, 200)
        self.assertEqual(len(event_id_filtered.json()), 1)
        self.assertEqual(event_id_filtered.json()[0]["source_event_id"], 303)

        self.assertEqual(date_filtered.status_code, 200)
        self.assertEqual(
            [row["source_event_id"] for row in date_filtered.json()],
            [303, 302],
        )

    def test_empty_results_return_200_with_empty_list(self) -> None:
        db = self._new_db()
        client = self._new_client(db)

        balance = client.get("/v2/stock-ledger/balance", params={"org_id": "ORG-EMPTY"})
        entries = client.get("/v2/stock-ledger/entries", params={"org_id": "ORG-EMPTY"})

        self.assertEqual(balance.status_code, 200)
        self.assertEqual(balance.json(), [])
        self.assertEqual(entries.status_code, 200)
        self.assertEqual(entries.json(), [])

    def test_validation_guards_reject_invalid_enum_date_and_pagination_inputs(self) -> None:
        db = self._new_db()
        client = self._new_client(db)

        invalid_balance_enum = client.get(
            "/v2/stock-ledger/balance",
            params={"org_id": "ORG-READ", "source_event_type": "BAD_EVENT"},
        )
        invalid_balance_date = client.get(
            "/v2/stock-ledger/balance",
            params={
                "org_id": "ORG-READ",
                "date_from": "2026-03-19",
                "date_to": "2026-03-18",
            },
        )
        invalid_entries_enum = client.get(
            "/v2/stock-ledger/entries",
            params={"org_id": "ORG-READ", "movement_type": "SIDEWAYS"},
        )
        invalid_entries_page = client.get(
            "/v2/stock-ledger/entries",
            params={"org_id": "ORG-READ", "page": 0},
        )
        invalid_entries_page_size = client.get(
            "/v2/stock-ledger/entries",
            params={"org_id": "ORG-READ", "page_size": 201},
        )

        self.assertEqual(invalid_balance_enum.status_code, 422)
        self.assertEqual(invalid_balance_date.status_code, 422)
        self.assertIn("date_from", invalid_balance_date.json()["detail"])

        self.assertEqual(invalid_entries_enum.status_code, 422)
        self.assertEqual(invalid_entries_page.status_code, 422)
        self.assertIn("page", invalid_entries_page.json()["detail"])
        self.assertEqual(invalid_entries_page_size.status_code, 422)
        self.assertIn("page_size", invalid_entries_page_size.json()["detail"])

    def test_read_surface_remains_read_only_and_keeps_rm_boundary_explicit(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        row = self._seed_ledger(
            db,
            item_code="RM-BOUNDARY",
            stock_bucket="RAW_MATERIAL",
            movement_type="OUT",
            txn_type="ISSUE",
            qty=-8.0,
            base_qty=8.0,
            base_uom="KG",
            source_event_type="RM_ISSUE",
            source_event_id=501,
            source_event_line_id=5501,
            posted_at=datetime(2026, 3, 18, 12, 0, 0),
            remark="current RM ledger net result is not full physical on-hand",
        )
        db.commit()

        before_values = (
            row.id,
            row.ledger_no,
            row.source_event_type,
            row.source_event_line_id,
            row.qty,
            row.base_qty,
            row.base_uom,
            row.posted_by,
            row.remark,
        )
        before_count = db.query(StockLedger).count()

        balance = client.get("/v2/stock-ledger/balance", params={"org_id": "ORG-READ"})
        entries = client.get("/v2/stock-ledger/entries", params={"org_id": "ORG-READ"})

        self.assertEqual(balance.status_code, 200)
        self.assertEqual(
            balance.json(),
            [
                {
                    "item_code": "RM-BOUNDARY",
                    "stock_bucket": "RAW_MATERIAL",
                    "base_uom": "KG",
                    "total_in_qty": 0.0,
                    "total_out_qty": 8.0,
                    "net_balance_qty": -8.0,
                    "last_posted_at": "2026-03-18T12:00:00",
                }
            ],
        )
        self.assertEqual(entries.status_code, 200)
        self.assertEqual(entries.json()[0]["source_event_line_id"], 5501)

        after_row = db.query(StockLedger).filter(StockLedger.id == row.id).first()
        assert after_row is not None
        after_values = (
            after_row.id,
            after_row.ledger_no,
            after_row.source_event_type,
            after_row.source_event_line_id,
            after_row.qty,
            after_row.base_qty,
            after_row.base_uom,
            after_row.posted_by,
            after_row.remark,
        )
        self.assertEqual(db.query(StockLedger).count(), before_count)
        self.assertEqual(after_values, before_values)


if __name__ == "__main__":
    unittest.main()
