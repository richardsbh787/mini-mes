from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v2.step47_phasea_declared_manual_intake import (
    get_step47_phasea_declared_manual_authenticated_identity,
    router,
)
from database import Base, get_db
from models import Step47PhaseADeclaredManualSource


def _make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


class Step47PhaseADeclaredManualIntakeTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def _new_client(self, db: Session, *, authenticated_identity: str = "verified-dev-operator") -> TestClient:
        app = FastAPI()
        app.include_router(router)

        def override_get_db():
            try:
                yield db
            finally:
                pass

        def override_authenticated_identity() -> str:
            return authenticated_identity

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_step47_phasea_declared_manual_authenticated_identity] = (
            override_authenticated_identity
        )
        client = TestClient(app)
        self.addCleanup(client.close)
        return client

    @contextmanager
    def _intake_boundary(self, *, env_name: str, intake_enabled: str):
        previous_env = os.environ.get("MINI_MES_ENV")
        previous_flag = os.environ.get("STEP47_PHASEA_DECLARED_MANUAL_INTAKE_ENABLED")
        os.environ["MINI_MES_ENV"] = env_name
        os.environ["STEP47_PHASEA_DECLARED_MANUAL_INTAKE_ENABLED"] = intake_enabled
        try:
            yield
        finally:
            if previous_env is None:
                os.environ.pop("MINI_MES_ENV", None)
            else:
                os.environ["MINI_MES_ENV"] = previous_env
            if previous_flag is None:
                os.environ.pop("STEP47_PHASEA_DECLARED_MANUAL_INTAKE_ENABLED", None)
            else:
                os.environ["STEP47_PHASEA_DECLARED_MANUAL_INTAKE_ENABLED"] = previous_flag

    def test_create_fails_when_minimum_audit_spine_fields_are_missing(self) -> None:
        db = self._new_db()
        client = self._new_client(db)

        with self._intake_boundary(env_name="test", intake_enabled="true"):
            missing_location = client.post(
                "/v2/step47-phasea-declared-manual-intake",
                json={"source_record_reference": "CARD-001"},
            )
            missing_reference = client.post(
                "/v2/step47-phasea-declared-manual-intake",
                json={"declared_location": "FG-LOC-A"},
            )

        self.assertEqual(missing_location.status_code, 422)
        self.assertIn("declared_location", missing_location.text)
        self.assertEqual(missing_reference.status_code, 422)
        self.assertIn("source_record_reference", missing_reference.text)

    def test_missing_source_record_reference_fails_explicitly(self) -> None:
        db = self._new_db()
        client = self._new_client(db)

        with self._intake_boundary(env_name="test", intake_enabled="true"):
            response = client.post(
                "/v2/step47-phasea-declared-manual-intake",
                json={"declared_location": "FG-LOC-A", "source_record_reference": ""},
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("source_record_reference", response.text)

    def test_successful_create_preserves_declared_manual_semantics(self) -> None:
        db = self._new_db()
        client = self._new_client(db, authenticated_identity="verified-token-user")
        before = datetime.utcnow()

        with self._intake_boundary(env_name="test", intake_enabled="true"):
            response = client.post(
                "/v2/step47-phasea-declared-manual-intake",
                json={
                    "declared_location": "fg-loc-a",
                    "source_record_reference": "CARD-001",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data_strength"], "declared_manual")
        self.assertFalse(payload["is_legal_truth"])
        self.assertEqual(payload["record"]["data_strength"], "declared_manual")
        self.assertFalse(payload["record"]["is_legal_truth"])
        self.assertTrue(payload["record"]["is_test_data"])
        self.assertEqual(payload["record"]["declared_by"], "verified-token-user")
        self.assertEqual(payload["record"]["declared_location"], "FG-LOC-A")
        self.assertEqual(payload["record"]["source_record_reference"], "CARD-001")
        self.assertNotIn("location", payload["record"])

        stored = db.query(Step47PhaseADeclaredManualSource).filter_by(id=payload["record"]["id"]).one()
        self.assertEqual(stored.declared_by, "verified-token-user")
        self.assertEqual(stored.declared_location, "FG-LOC-A")
        self.assertEqual(stored.source_record_reference, "CARD-001")
        self.assertIsNotNone(stored.declared_at)
        self.assertGreaterEqual(stored.declared_at, before)

    def test_overwrite_misuse_is_explicitly_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)

        with self._intake_boundary(env_name="test", intake_enabled="true"):
            response = client.post(
                "/v2/step47-phasea-declared-manual-intake",
                json={
                    "declared_location": "FG-LOC-A",
                    "source_record_reference": "CARD-001",
                    "overwrite_target_id": 7,
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn("create-only", response.json()["detail"])
        self.assertIn("overwrite", response.json()["detail"])

    def test_correction_misuse_is_explicitly_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db)

        with self._intake_boundary(env_name="test", intake_enabled="true"):
            response = client.post(
                "/v2/step47-phasea-declared-manual-intake",
                json={
                    "declared_location": "FG-LOC-A",
                    "source_record_reference": "CARD-001",
                    "correction_target_id": 9,
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn("create-only", response.json()["detail"])
        self.assertIn("correction", response.json()["detail"])

    def test_bulk_create_array_payload_is_explicitly_blocked(self) -> None:
        db = self._new_db()
        client = self._new_client(db)

        with self._intake_boundary(env_name="test", intake_enabled="true"):
            response = client.post(
                "/v2/step47-phasea-declared-manual-intake",
                json=[
                    {
                        "declared_location": "FG-LOC-A",
                        "source_record_reference": "CARD-001",
                    }
                ],
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            "Step 47 Phase A declared/manual intake accepts one record only and rejects bulk or array payloads",
        )

    def test_request_body_declared_by_and_declared_at_are_explicitly_rejected(self) -> None:
        db = self._new_db()
        client = self._new_client(db, authenticated_identity="trusted-session-user")

        with self._intake_boundary(env_name="test", intake_enabled="true"):
            declared_by_response = client.post(
                "/v2/step47-phasea-declared-manual-intake",
                json={
                    "declared_by": "client-user",
                    "declared_location": "FG-LOC-A",
                    "source_record_reference": "CARD-001",
                },
            )
            declared_at_response = client.post(
                "/v2/step47-phasea-declared-manual-intake",
                json={
                    "declared_at": "2026-04-10T10:00:00",
                    "declared_location": "FG-LOC-A",
                    "source_record_reference": "CARD-001",
                },
            )

        self.assertEqual(declared_by_response.status_code, 422)
        self.assertEqual(
            declared_by_response.json()["detail"],
            "client-supplied field is forbidden for Step 47 Phase A declared/manual intake: declared_by",
        )
        self.assertEqual(declared_at_response.status_code, 422)
        self.assertEqual(
            declared_at_response.json()["detail"],
            "client-supplied field is forbidden for Step 47 Phase A declared/manual intake: declared_at",
        )
        self.assertEqual(db.query(Step47PhaseADeclaredManualSource).count(), 0)

    def test_route_is_unavailable_outside_dev_test_boundary(self) -> None:
        db = self._new_db()
        client = self._new_client(db)

        with self._intake_boundary(env_name="production", intake_enabled="true"):
            response = client.post(
                "/v2/step47-phasea-declared-manual-intake",
                json={
                    "declared_location": "FG-LOC-A",
                    "source_record_reference": "CARD-001",
                },
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["detail"],
            "Step 47 Phase A declared/manual intake is unavailable outside the approved dev/test boundary",
        )


if __name__ == "__main__":
    unittest.main()
