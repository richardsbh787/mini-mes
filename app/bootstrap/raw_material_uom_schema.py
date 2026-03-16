from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_raw_material_uom_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    if not inspector.has_table("raw_materials"):
        return

    existing_columns = {col["name"] for col in inspector.get_columns("raw_materials")}
    statements: list[str] = []
    if "conversion_type" not in existing_columns:
        statements.append("ALTER TABLE raw_materials ADD COLUMN conversion_type VARCHAR")
    if "standard_conversion_ratio" not in existing_columns:
        statements.append("ALTER TABLE raw_materials ADD COLUMN standard_conversion_ratio FLOAT")

    with engine.begin() as conn:
        for sql in statements:
            conn.execute(text(sql))

        if "conversion_type" not in existing_columns:
            conn.execute(
                text(
                    "UPDATE raw_materials "
                    "SET conversion_type = 'STANDARD' "
                    "WHERE conversion_type IS NULL OR TRIM(conversion_type) = ''"
                )
            )
        if "standard_conversion_ratio" not in existing_columns:
            conn.execute(
                text(
                    "UPDATE raw_materials "
                    "SET standard_conversion_ratio = 1.0 "
                    "WHERE standard_conversion_ratio IS NULL"
                )
            )
