from __future__ import annotations

import os
import unittest
from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v2.step47_phasea_declared_manual_read import router
from app.schemas.step47_phasea_declared_manual import (
    Step47PhaseADeclaredManualCorrection,
    Step47PhaseADeclaredManualCreate,
)
from app.services.step47_phasea_declared_manual import (
    correct_step47_phasea_declared_manual_source,
    create_step47_phasea_declared_manual_source,
)
from database import get_db
from tests.test_step47_phasea_declared_manual_storage_read_source import _make_session


class Step47PhaseADeclaredManualReadSurfaceTests(unittest.TestCase):
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

    @contextmanager
    def _phasea_read_boundary(self, *, env_name: str, read_enabled: str):
        previous_env = os.environ.get("MINI_MES_ENV")
        previous_flag = os.environ.get("STEP47_PHASEA_DECLARED_MANUAL_READ_ENABLED")
        os.environ["MINI_MES_ENV"] = env_name
        os.environ["STEP47_PHASEA_DECLARED_MANUAL_READ_ENABLED"] = read_enabled
        try:
            yield
        finally:
            if previous_env is None:
                os.environ.pop("MINI_MES_ENV", None)
            else:
                os.environ["MINI_MES_ENV"] = previous_env
            if previous_flag is None:
                os.environ.pop("STEP47_PHASEA_DECLARED_MANUAL_READ_ENABLED", None)
            else:
                os.environ["STEP47_PHASEA_DECLARED_MANUAL_READ_ENABLED"] = previous_flag

    def _assert_consumer_legal_truth_use_blocked(self, payload: dict) -> None:
        assert payload["is_legal_truth"] is True, (
            "consumer misuse blocked: Step47 PhaseA declared/manual read surface is not legal truth"
        )

    def test_list_surface_returns_declared_manual_records_with_audit_spine(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        first = create_step47_phasea_declared_manual_source(
            db,
            payload=Step47PhaseADeclaredManualCreate(
                declared_by="operator-a",
                declared_location="FG-LOC-A",
                source_record_reference="CARD-001",
            ),
        )
        second = create_step47_phasea_declared_manual_source(
            db,
            payload=Step47PhaseADeclaredManualCreate(
                declared_by="operator-b",
                declared_location="FG-LOC-B",
                source_record_reference="CARD-002",
            ),
        )
        db.commit()

        with self._phasea_read_boundary(env_name="test", read_enabled="true"):
            response = client.get(
                "/v2/step47-phasea-declared-manual-records",
                params={"page": 1, "page_size": 20},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data_strength"], "declared_manual")
        self.assertFalse(payload["is_legal_truth"])
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["page_size"], 20)
        self.assertEqual(payload["total_count"], 2)
        self.assertEqual([item["id"] for item in payload["items"]], [second.id, first.id])
        self.assertEqual(payload["items"][0]["data_strength"], "declared_manual")
        self.assertFalse(payload["items"][0]["is_legal_truth"])
        self.assertTrue(payload["items"][0]["is_test_data"])
        self.assertEqual(payload["items"][0]["declared_by"], "operator-b")
        self.assertEqual(payload["items"][0]["declared_location"], "FG-LOC-B")
        self.assertEqual(payload["items"][0]["source_record_reference"], "CARD-002")
        self.assertNotIn("location", payload["items"][0])

    def test_detail_surface_preserves_declared_manual_identity_only(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        created = create_step47_phasea_declared_manual_source(
            db,
            payload=Step47PhaseADeclaredManualCreate(
                declared_by="operator-a",
                declared_location="FG-LOC-A",
                source_record_reference="CARD-001",
            ),
        )
        db.commit()
        correct_step47_phasea_declared_manual_source(
            db,
            declaration_id=created.id,
            payload=Step47PhaseADeclaredManualCorrection(
                corrected_by="supervisor-a",
                correction_reason="source card misread",
                declared_location="FG-LOC-B",
                source_record_reference="CARD-002",
            ),
        )
        db.commit()

        with self._phasea_read_boundary(env_name="test", read_enabled="true"):
            response = client.get(
                "/v2/step47-phasea-declared-manual-records/detail",
                params={"declaration_id": created.id},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data_strength"], "declared_manual")
        self.assertFalse(payload["is_legal_truth"])
        self.assertEqual(payload["current_record"]["data_strength"], "declared_manual")
        self.assertFalse(payload["current_record"]["is_legal_truth"])
        self.assertTrue(payload["current_record"]["is_test_data"])
        self.assertEqual(payload["current_record"]["declared_location"], "FG-LOC-B")
        self.assertEqual(payload["original_record"]["data_strength"], "declared_manual")
        self.assertFalse(payload["original_record"]["is_legal_truth"])
        self.assertTrue(payload["original_record"]["is_test_data"])
        self.assertEqual(payload["original_record"]["declared_location"], "FG-LOC-A")
        self.assertEqual(payload["correction_trace"][0]["data_strength"], "declared_manual")
        self.assertFalse(payload["correction_trace"][0]["is_legal_truth"])
        self.assertTrue(payload["correction_trace"][0]["is_test_data"])
        self.assertEqual(payload["correction_trace"][0]["correction_reason"], "source card misread")
        self.assertNotIn("location", payload["current_record"])
        self.assertNotIn("location", payload["original_record"])

    def test_read_surface_has_no_summary_path_and_no_write_action(self) -> None:
        db = self._new_db()
        client = self._new_client(db)

        with self._phasea_read_boundary(env_name="test", read_enabled="true"):
            summary = client.get("/v2/step47-phasea-declared-manual-records/summary")
            create_attempt = client.post(
                "/v2/step47-phasea-declared-manual-records",
                json={
                    "declared_by": "operator-a",
                    "declared_location": "FG-LOC-A",
                    "source_record_reference": "CARD-001",
                },
            )

        self.assertEqual(summary.status_code, 404)
        self.assertEqual(create_attempt.status_code, 405)

    def test_detail_missing_record_returns_404_without_summary_fallback(self) -> None:
        db = self._new_db()
        client = self._new_client(db)

        with self._phasea_read_boundary(env_name="test", read_enabled="true"):
            response = client.get(
                "/v2/step47-phasea-declared-manual-records/detail",
                params={"declaration_id": 999},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Step 47 Phase A declared/manual source record not found")

    def test_read_surface_is_blocked_outside_explicit_dev_test_boundary(self) -> None:
        db = self._new_db()
        client = self._new_client(db)

        with self._phasea_read_boundary(env_name="production", read_enabled="true"):
            response = client.get(
                "/v2/step47-phasea-declared-manual-records",
                params={"page": 1, "page_size": 20},
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["detail"],
            "Step 47 Phase A declared/manual read surface is unavailable outside the approved dev/test boundary",
        )

    def test_consumer_misuse_is_blocked_by_explicit_non_legal_truth_assertion(self) -> None:
        db = self._new_db()
        client = self._new_client(db)
        create_step47_phasea_declared_manual_source(
            db,
            payload=Step47PhaseADeclaredManualCreate(
                declared_by="operator-a",
                declared_location="FG-LOC-A",
                source_record_reference="CARD-001",
            ),
        )
        db.commit()

        with self._phasea_read_boundary(env_name="test", read_enabled="true"):
            response = client.get(
                "/v2/step47-phasea-declared-manual-records",
                params={"page": 1, "page_size": 20},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        with self.assertRaisesRegex(
            AssertionError,
            "consumer misuse blocked: Step47 PhaseA declared/manual read surface is not legal truth",
        ):
            self._assert_consumer_legal_truth_use_blocked(payload)


if __name__ == "__main__":
    unittest.main()
