from __future__ import annotations

import os
import tempfile
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.bootstrap.raw_material_uom_schema import ensure_raw_material_uom_columns
from database import Base
from main import create_raw_material
from models import RawMaterial
from schemas import RawMaterialCreate


class RawMaterialUomSchemaBootstrapTests(unittest.TestCase):
    def _new_engine(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        engine = create_engine(f"sqlite:///{path}")
        self.addCleanup(engine.dispose)
        return engine

    def test_bootstrap_adds_conversion_columns_and_backfills_defaults(self) -> None:
        engine = self._new_engine()

        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE TABLE raw_materials ("
                    "id INTEGER PRIMARY KEY, "
                    "material_code VARCHAR NOT NULL, "
                    "material_name VARCHAR NOT NULL, "
                    "unit VARCHAR NOT NULL"
                    ")"
                )
            )
            conn.execute(
                text(
                    "INSERT INTO raw_materials (id, material_code, material_name, unit) "
                    "VALUES (1, 'RM-1', 'Material 1', 'PCS')"
                )
            )

        ensure_raw_material_uom_columns(engine)

        inspector = inspect(engine)
        columns = {col["name"] for col in inspector.get_columns("raw_materials")}
        self.assertTrue({"conversion_type", "standard_conversion_ratio"}.issubset(columns))

        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT conversion_type, standard_conversion_ratio "
                    "FROM raw_materials WHERE id = 1"
                )
            ).one()

        self.assertEqual(row[0], "STANDARD")
        self.assertEqual(row[1], 1.0)


class RawMaterialUomSchemaValidationTests(unittest.TestCase):
    def test_schema_accepts_standard_and_lot_actual_placeholders(self) -> None:
        standard = RawMaterialCreate(
            material_code="RM-STD",
            material_name="Standard Material",
            unit="PCS",
            conversion_type=" standard ",
            standard_conversion_ratio=2.5,
        )
        lot_actual = RawMaterialCreate(
            material_code="RM-LOT",
            material_name="Lot Actual Material",
            unit="KG",
            conversion_type="lot_actual",
            standard_conversion_ratio=1.0,
        )

        self.assertEqual(standard.conversion_type, "STANDARD")
        self.assertEqual(lot_actual.conversion_type, "LOT_ACTUAL")

    def test_schema_rejects_invalid_conversion_type(self) -> None:
        with self.assertRaises(ValueError) as exc:
            RawMaterialCreate(
                material_code="RM-BAD",
                material_name="Bad Material",
                unit="PCS",
                conversion_type="CUSTOM",
                standard_conversion_ratio=1.0,
            )

        self.assertIn("conversion_type must be STANDARD or LOT_ACTUAL", str(exc.exception))


class RawMaterialUomSchemaCreateTests(unittest.TestCase):
    def _new_db(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        ensure_raw_material_uom_columns(engine)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        self.addCleanup(engine.dispose)
        self.addCleanup(db.close)
        return db

    def test_create_raw_material_persists_conversion_fields(self) -> None:
        db = self._new_db()

        created = create_raw_material(
            RawMaterialCreate(
                material_code="RM-100",
                material_name="Material 100",
                unit="PCS",
                conversion_type="STANDARD",
                standard_conversion_ratio=12.0,
            ),
            db=db,
        )

        row = db.query(RawMaterial).filter(RawMaterial.id == created.id).one()
        self.assertEqual(row.conversion_type, "STANDARD")
        self.assertEqual(row.standard_conversion_ratio, 12.0)

    def test_create_raw_material_defaults_standard_foundation(self) -> None:
        db = self._new_db()

        created = create_raw_material(
            RawMaterialCreate(
                material_code="RM-101",
                material_name="Material 101",
                unit="KG",
            ),
            db=db,
        )

        self.assertEqual(created.conversion_type, "STANDARD")
        self.assertEqual(created.standard_conversion_ratio, 1.0)


if __name__ == "__main__":
    unittest.main()
