from __future__ import annotations

import unittest
from datetime import datetime

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.schemas.step47_phasea_declared_manual import (
    Step47PhaseADeclaredManualCorrection,
    Step47PhaseADeclaredManualCreate,
)
from app.services.step47_phasea_declared_manual import (
    _build_original_record,
    correct_step47_phasea_declared_manual_source,
    create_step47_phasea_declared_manual_source,
    get_step47_phasea_declared_manual_source_detail,
    list_step47_phasea_declared_manual_sources_internal,
)
from database import Base
from models import (
    Step47PhaseADeclaredManualCorrectionTrace,
    Step47PhaseADeclaredManualSource,
)


def _make_session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)()


class Step47PhaseADeclaredManualStorageReadSourceTests(unittest.TestCase):
    def _new_db(self) -> Session:
        db = _make_session()
        self.addCleanup(db.close)
        return db

    def test_create_rejects_client_provided_declared_at(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            Step47PhaseADeclaredManualCreate.model_validate(
                {
                    "declared_by": "operator-a",
                    "declared_at": "2026-04-07T10:00:00",
                    "declared_location": "FG-LOC-A",
                    "source_record_reference": "CARD-001",
                }
            )

        self.assertIn("declared_at", str(ctx.exception))

    def test_create_generates_declared_at_in_system_and_requires_full_audit_spine(self) -> None:
        db = self._new_db()
        before = datetime.utcnow()
        created = create_step47_phasea_declared_manual_source(
            db,
            payload=Step47PhaseADeclaredManualCreate(
                declared_by="operator-a",
                declared_location="fg-loc-a",
                source_record_reference="CARD-001",
            ),
        )
        db.commit()

        self.assertEqual(created.declared_by, "operator-a")
        self.assertEqual(created.declared_location, "FG-LOC-A")
        self.assertEqual(created.source_record_reference, "CARD-001")
        self.assertGreaterEqual(created.declared_at, before)
        stored = db.query(Step47PhaseADeclaredManualSource).filter_by(id=created.id).one()
        self.assertEqual(stored.declared_by, "operator-a")
        self.assertIsNotNone(stored.declared_at)

        with self.assertRaises(ValidationError):
            Step47PhaseADeclaredManualCreate(
                declared_by="operator-a",
                declared_location="FG-LOC-A",
                source_record_reference="",
            )

    def test_declared_location_rejects_unstructured_free_text(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            Step47PhaseADeclaredManualCreate(
                declared_by="operator-a",
                declared_location="rack 1 left side",
                source_record_reference="CARD-001",
            )

        self.assertIn("declared_location", str(ctx.exception))

    def test_internal_read_methods_return_declared_manual_source_only(self) -> None:
        db = self._new_db()
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

        listed = list_step47_phasea_declared_manual_sources_internal(db)
        self.assertEqual([row.id for row in listed], [second.id, first.id])
        detail = get_step47_phasea_declared_manual_source_detail(db, declaration_id=first.id)
        self.assertEqual(detail.current_record.declared_location, "FG-LOC-A")
        self.assertEqual(detail.original_record.declared_location, "FG-LOC-A")
        self.assertEqual(detail.correction_trace, [])
        self.assertEqual(detail.data_strength, "declared_manual")
        self.assertFalse(detail.is_legal_truth)
        self.assertEqual(detail.current_record.data_strength, "declared_manual")
        self.assertFalse(detail.current_record.is_legal_truth)
        self.assertTrue(detail.current_record.is_test_data)
        self.assertEqual(detail.original_record.data_strength, "declared_manual")
        self.assertFalse(detail.original_record.is_legal_truth)
        self.assertTrue(detail.original_record.is_test_data)

    def test_correction_preserves_trace_and_keeps_original_values_queryable(self) -> None:
        db = self._new_db()
        created = create_step47_phasea_declared_manual_source(
            db,
            payload=Step47PhaseADeclaredManualCreate(
                declared_by="operator-a",
                declared_location="FG-LOC-A",
                source_record_reference="CARD-001",
            ),
        )
        db.commit()

        detail = correct_step47_phasea_declared_manual_source(
            db,
            declaration_id=created.id,
            payload=Step47PhaseADeclaredManualCorrection(
                corrected_by="supervisor-a",
                declared_location="FG-LOC-B",
                source_record_reference="CARD-002",
            ),
        )
        db.commit()

        self.assertEqual(detail.current_record.declared_location, "FG-LOC-B")
        self.assertEqual(detail.current_record.source_record_reference, "CARD-002")
        self.assertEqual(detail.original_record.declared_location, "FG-LOC-A")
        self.assertEqual(detail.original_record.source_record_reference, "CARD-001")
        self.assertEqual(len(detail.correction_trace), 1)
        trace = detail.correction_trace[0]
        self.assertEqual(trace.data_strength, "declared_manual")
        self.assertFalse(trace.is_legal_truth)
        self.assertTrue(trace.is_test_data)
        self.assertEqual(trace.corrected_by, "supervisor-a")
        self.assertEqual(trace.previous_declared_location, "FG-LOC-A")
        self.assertEqual(trace.new_declared_location, "FG-LOC-B")
        self.assertEqual(trace.previous_source_record_reference, "CARD-001")
        self.assertEqual(trace.new_source_record_reference, "CARD-002")
        stored_trace = db.query(Step47PhaseADeclaredManualCorrectionTrace).filter_by(declaration_id=created.id).one()
        self.assertEqual(stored_trace.previous_declared_location, "FG-LOC-A")

    def test_correction_rejects_noop_overwrite_attempt(self) -> None:
        db = self._new_db()
        created = create_step47_phasea_declared_manual_source(
            db,
            payload=Step47PhaseADeclaredManualCreate(
                declared_by="operator-a",
                declared_location="FG-LOC-A",
                source_record_reference="CARD-001",
            ),
        )
        db.commit()

        with self.assertRaises(HTTPException) as ctx:
            correct_step47_phasea_declared_manual_source(
                db,
                declaration_id=created.id,
                payload=Step47PhaseADeclaredManualCorrection(
                    corrected_by="supervisor-a",
                    declared_location="FG-LOC-A",
                    source_record_reference="CARD-001",
                ),
            )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(
            db.query(Step47PhaseADeclaredManualCorrectionTrace).filter_by(declaration_id=created.id).count(),
            0,
        )

    def test_correction_payload_rejects_declared_by_mutation_attempt(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            Step47PhaseADeclaredManualCorrection.model_validate(
                {
                    "corrected_by": "supervisor-a",
                    "declared_by": "operator-b",
                    "declared_location": "FG-LOC-B",
                }
            )

        self.assertIn("declared_by", str(ctx.exception))

    def test_build_original_record_sorts_trace_order_internally(self) -> None:
        db = self._new_db()
        created = create_step47_phasea_declared_manual_source(
            db,
            payload=Step47PhaseADeclaredManualCreate(
                declared_by="operator-a",
                declared_location="FG-LOC-C",
                source_record_reference="CARD-003",
            ),
        )
        db.commit()
        row = db.query(Step47PhaseADeclaredManualSource).filter_by(id=created.id).one()

        first_trace = Step47PhaseADeclaredManualCorrectionTrace(
            declaration_id=row.id,
            corrected_by="supervisor-a",
            corrected_at=datetime(2026, 4, 7, 10, 0, 0),
            previous_declared_location="FG-LOC-A",
            new_declared_location="FG-LOC-B",
            previous_source_record_reference="CARD-001",
            new_source_record_reference="CARD-002",
        )
        second_trace = Step47PhaseADeclaredManualCorrectionTrace(
            declaration_id=row.id,
            corrected_by="supervisor-b",
            corrected_at=datetime(2026, 4, 7, 11, 0, 0),
            previous_declared_location="FG-LOC-B",
            new_declared_location="FG-LOC-C",
            previous_source_record_reference="CARD-002",
            new_source_record_reference="CARD-003",
        )

        original = _build_original_record(row=row, traces=[second_trace, first_trace])
        self.assertEqual(original.declared_location, "FG-LOC-A")
        self.assertEqual(original.source_record_reference, "CARD-001")
        self.assertEqual(original.data_strength, "declared_manual")
        self.assertFalse(original.is_legal_truth)
        self.assertTrue(original.is_test_data)


if __name__ == "__main__":
    unittest.main()
