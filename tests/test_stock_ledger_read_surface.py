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
        txn_qty: float | None = None,
        txn_uom: str | None = None,
        source_event_type: str | None = None,
        source_event_id: int | None = None,
        source_event_line_id: int | None = None,
        posted_by: str = "reader",
        posted_at: datetime | None = None,
        remark: str | None = None,
        work_order_id: int | None = None,
        sales_order_id: int | None = None,
    ) -> StockLedger:
        row = StockLedger(
            org_id=org_id,
            ledger_no=f"SLED-{item_code}-{movement_type}-{source_event_id or 0}-{source_event_line_id or 0}",
            item_id=item_code,
            item_code=item_code,
            txn_type=txn_type,
            movement_type=movement_type,
            stock_bucket=stock_bucket,
            qty=qty,
            uom=base_uom,
            txn_qty=txn_qty if txn_qty is not None else abs(qty),
            txn_uom=txn_uom or base_uom,
            base_qty=base_qty,
            base_uom=base_uom,
            source_event_type=source_event_type,
            source_event_id=source_event_id,
            source_event_line_id=source_event_line_id,
            posted_by=posted_by,
            posted_at=posted_at or datetime(2026, 3, 18, 8, 0, 0),
            occurred_at=posted_at or datetime(2026, 3, 18, 8, 0, 0),
            remark=remark,
            work_order_id=work_order_id,
            sales_order_id=sales_order_id,
        )
        db.add(row)
        db.flush()
        return row

    def test_balance_returns_full_aggregated_result_grouped_by_item_bucket_and_base_uom(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        self._seed_ledger(
            db,
            item_code="RM-100",
            stock_bucket="RAW_MATERIAL",
            movement_type="IN",
            txn_type="RECEIPT",
            qty=10.0,
            base_qty=10.0,
            base_uom="KG",
            source_event_type="ADJUSTMENT",
            source_event_id=1,
        )
        self._seed_ledger(
            db,
            item_code="RM-100",
            stock_bucket="RAW_MATERIAL",
            movement_type="OUT",
            txn_type="ISSUE",
            qty=-4.0,
            base_qty=4.0,
            base_uom="KG",
            source_event_type="RM_ISSUE",
            source_event_id=2,
            source_event_line_id=21,
        )
        self._seed_ledger(
            db,
            item_code="RM-100",
            stock_bucket="RAW_MATERIAL",
            movement_type="IN",
            txn_type="RECEIPT",
            qty=3.0,
            base_qty=3.0,
            base_uom="BOX",
            source_event_type="ADJUSTMENT",
            source_event_id=3,
        )
        self._seed_ledger(
            db,
            item_code="FG-200",
            stock_bucket="FINISHED_GOODS",
            movement_type="IN",
            txn_type="RECEIPT",
            qty=7.0,
            base_qty=7.0,
            base_uom="PCS",
            source_event_type="FG_RECEIVE",
            source_event_id=4,
        )
        db.commit()

        response = client.get("/v2/stock-ledger/balance", params={"org_id": "ORG-READ"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {"item_code": "FG-200", "stock_bucket": "FINISHED_GOODS", "base_uom": "PCS", "net_base_qty": 7.0},
                {"item_code": "RM-100", "stock_bucket": "RAW_MATERIAL", "base_uom": "BOX", "net_base_qty": 3.0},
                {"item_code": "RM-100", "stock_bucket": "RAW_MATERIAL", "base_uom": "KG", "net_base_qty": 6.0},
            ],
        )

    def test_balance_applies_source_event_type_as_filter_not_grouping_key(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        self._seed_ledger(
            db,
            item_code="RM-200",
            stock_bucket="RAW_MATERIAL",
            movement_type="OUT",
            txn_type="ISSUE",
            qty=-5.0,
            base_qty=5.0,
            base_uom="PCS",
            source_event_type="RM_ISSUE",
            source_event_id=11,
            source_event_line_id=101,
        )
        self._seed_ledger(
            db,
            item_code="RM-200",
            stock_bucket="RAW_MATERIAL",
            movement_type="OUT",
            txn_type="ISSUE",
            qty=-2.0,
            base_qty=2.0,
            base_uom="PCS",
            source_event_type="RM_ISSUE",
            source_event_id=12,
            source_event_line_id=102,
        )
        self._seed_ledger(
            db,
            item_code="RM-200",
            stock_bucket="RAW_MATERIAL",
            movement_type="IN",
            txn_type="RECEIPT",
            qty=9.0,
            base_qty=9.0,
            base_uom="PCS",
            source_event_type="ADJUSTMENT",
            source_event_id=13,
        )
        db.commit()

        filtered = client.get(
            "/v2/stock-ledger/balance",
            params={"org_id": "ORG-READ", "source_event_type": "RM_ISSUE"},
        )
        all_rows = client.get("/v2/stock-ledger/balance", params={"org_id": "ORG-READ"})

        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.json(), [{"item_code": "RM-200", "stock_bucket": "RAW_MATERIAL", "base_uom": "PCS", "net_base_qty": -7.0}])
        self.assertEqual(all_rows.status_code, 200)
        self.assertEqual(all_rows.json(), [{"item_code": "RM-200", "stock_bucket": "RAW_MATERIAL", "base_uom": "PCS", "net_base_qty": 2.0}])

    def test_entries_support_pagination_and_expose_source_event_line_id_boundary(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        self._seed_ledger(
            db,
            item_code="RM-300",
            stock_bucket="RAW_MATERIAL",
            movement_type="OUT",
            txn_type="ISSUE",
            qty=-2.0,
            base_qty=2.0,
            base_uom="PCS",
            source_event_type="RM_ISSUE",
            source_event_id=31,
            source_event_line_id=301,
            posted_at=datetime(2026, 3, 18, 8, 0, 0),
            work_order_id=301,
            sales_order_id=401,
        )
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
            source_event_id=32,
            source_event_line_id=302,
            posted_at=datetime(2026, 3, 18, 9, 0, 0),
            work_order_id=302,
            sales_order_id=402,
        )
        self._seed_ledger(
            db,
            item_code="FG-301",
            stock_bucket="FINISHED_GOODS",
            movement_type="OUT",
            txn_type="ISSUE",
            qty=-1.0,
            base_qty=1.0,
            base_uom="PCS",
            source_event_type="SHIPMENT",
            source_event_id=33,
            source_event_line_id=303,
            posted_at=datetime(2026, 3, 18, 10, 0, 0),
            work_order_id=303,
            sales_order_id=403,
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
        first_payload = first_page.json()
        self.assertEqual(len(first_payload), 2)
        self.assertEqual([row["source_event_type"] for row in first_payload], ["SHIPMENT", "FG_RECEIVE"])
        self.assertEqual(first_payload[0]["source_event_line_id"], None)
        self.assertEqual(first_payload[1]["source_event_line_id"], None)

        self.assertEqual(second_page.status_code, 200)
        second_payload = second_page.json()
        self.assertEqual(len(second_payload), 1)
        self.assertEqual(second_payload[0]["source_event_type"], "RM_ISSUE")
        self.assertEqual(second_payload[0]["source_event_line_id"], 301)
        self.assertEqual(second_payload[0]["base_qty"], 2.0)
        self.assertEqual(second_payload[0]["base_uom"], "PCS")

    def test_entries_filter_and_empty_result_return_200_with_empty_list(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        self._seed_ledger(
            db,
            item_code="FG-400",
            stock_bucket="FINISHED_GOODS",
            movement_type="IN",
            txn_type="RECEIPT",
            qty=2.0,
            base_qty=2.0,
            base_uom="PCS",
            source_event_type="FG_RECEIVE",
            source_event_id=41,
            posted_at=datetime(2026, 3, 18, 11, 0, 0),
        )
        db.commit()

        filtered = client.get(
            "/v2/stock-ledger/entries",
            params={"org_id": "ORG-READ", "source_event_type": "SHIPMENT"},
        )
        empty_balance = client.get("/v2/stock-ledger/balance", params={"org_id": "ORG-EMPTY"})

        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.json(), [])
        self.assertEqual(empty_balance.status_code, 200)
        self.assertEqual(empty_balance.json(), [])

    def test_read_surface_does_not_write_mutate_or_change_step39_rows(self) -> None:
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
            source_event_id=51,
            source_event_line_id=501,
            posted_at=datetime(2026, 3, 18, 12, 0, 0),
            remark="rm ledger net is issue-only truth",
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
        self.assertEqual(balance.json(), [{"item_code": "RM-BOUNDARY", "stock_bucket": "RAW_MATERIAL", "base_uom": "KG", "net_base_qty": -8.0}])
        self.assertEqual(entries.status_code, 200)
        self.assertEqual(entries.json()[0]["source_event_line_id"], 501)

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
