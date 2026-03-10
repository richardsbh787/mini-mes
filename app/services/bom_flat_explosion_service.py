from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import BOMHeader, BOMLine, BOMVersion


@dataclass
class _FlatLine:
    item_code: str
    total_qty: float
    uom: str
    sources: list["_FlatLeafSource"] = field(default_factory=list)


@dataclass(frozen=True)
class _FlatLeafSource:
    path: tuple[str, ...]
    parent_lineage: tuple[str, ...]
    is_phantom: bool
    leaf_reason: str
    exploded_from_version: int


class BOMFlatExplosionService:
    @staticmethod
    def _is_date_effective(version: BOMVersion, on_date: date) -> bool:
        if version.effective_from and on_date < version.effective_from:
            return False
        if version.effective_to and on_date > version.effective_to:
            return False
        return True

    def _pick_header_by_parent_code(self, db: Session, parent_code: str) -> BOMHeader:
        headers = (
            db.query(BOMHeader)
            .filter(BOMHeader.parent_system_item_code == parent_code)
            .order_by(BOMHeader.bom_id.desc())
            .all()
        )
        if not headers:
            raise HTTPException(status_code=404, detail=f"BOM header not found for {parent_code}")

        active_header = next((h for h in headers if str(h.status).upper() == "ACTIVE"), None)
        if not active_header:
            raise HTTPException(status_code=400, detail=f"BOM header is OBSOLETE for {parent_code}")
        return active_header

    def _pick_active_effective_version(self, db: Session, bom_id: int, on_date: date) -> BOMVersion:
        candidates = (
            db.query(BOMVersion)
            .filter(BOMVersion.bom_id == bom_id)
            .filter(func.upper(BOMVersion.status) == "ACTIVE")
            .order_by(BOMVersion.version_id.desc())
            .all()
        )
        for v in candidates:
            if self._is_date_effective(v, on_date):
                return v
        raise HTTPException(status_code=404, detail="No valid version found")

    def _pick_version_for_root(
        self,
        db: Session,
        header: BOMHeader,
        on_date: date,
        version_id: int | None,
    ) -> BOMVersion:
        if version_id is None:
            return self._pick_active_effective_version(db, header.bom_id, on_date)

        version = db.query(BOMVersion).filter(BOMVersion.version_id == version_id).first()
        if not version or version.bom_id != header.bom_id:
            raise HTTPException(status_code=404, detail="No valid version found")
        if str(version.status).upper() != "ACTIVE":
            raise HTTPException(status_code=400, detail="BOM version is not ACTIVE")
        if not self._is_date_effective(version, on_date):
            raise HTTPException(status_code=404, detail="No valid version found")
        return version

    def _try_pick_child_header_and_version(
        self,
        db: Session,
        parent_code: str,
        on_date: date,
    ) -> tuple[BOMHeader, BOMVersion] | None:
        headers = (
            db.query(BOMHeader)
            .filter(BOMHeader.parent_system_item_code == parent_code)
            .order_by(BOMHeader.bom_id.desc())
            .all()
        )
        if not headers:
            return None

        active_header = next((h for h in headers if str(h.status).upper() == "ACTIVE"), None)
        if not active_header:
            raise HTTPException(status_code=400, detail=f"BOM header is OBSOLETE for {parent_code}")

        version = self._pick_active_effective_version(db, active_header.bom_id, on_date)
        return active_header, version

    @staticmethod
    def _merge_line(
        flat: dict[str, _FlatLine],
        item_code: str,
        qty: float,
        uom: str,
        source: _FlatLeafSource,
    ) -> None:
        if item_code in flat:
            flat[item_code].total_qty += qty
            flat[item_code].sources.append(source)
            return
        flat[item_code] = _FlatLine(
            item_code=item_code,
            total_qty=qty,
            uom=uom,
            sources=[source],
        )

    def _explode_from_version(
        self,
        db: Session,
        version: BOMVersion,
        parent_required_qty: float,
        on_date: date,
        path: list[str],
        flat: dict[str, _FlatLine],
    ) -> None:
        lines = (
            db.query(BOMLine)
            .filter(BOMLine.version_id == version.version_id)
            .order_by(BOMLine.sequence.asc(), BOMLine.bom_line_id.asc())
            .all()
        )

        for line in lines:
            child_code = line.component_system_item_code
            if child_code in path:
                cycle_path = " -> ".join(path + [child_code])
                raise HTTPException(status_code=400, detail=f"Cycle detected: {cycle_path}")

            child_required_qty = parent_required_qty * float(line.qty_per) * (1 + float(line.scrap_rate))
            child_path = path + [child_code]

            child_target = self._try_pick_child_header_and_version(db, child_code, on_date)
            if child_target:
                _, child_version = child_target
                self._explode_from_version(
                    db=db,
                    version=child_version,
                    parent_required_qty=child_required_qty,
                    on_date=on_date,
                    path=child_path,
                    flat=flat,
                )
                continue

            if not line.phantom_flag:
                self._merge_line(
                    flat=flat,
                    item_code=child_code,
                    qty=child_required_qty,
                    uom=line.uom,
                    source=_FlatLeafSource(
                        path=tuple(child_path),
                        parent_lineage=tuple(path),
                        is_phantom=bool(line.phantom_flag),
                        leaf_reason="NO_CHILD_BOM",
                        exploded_from_version=version.version_id,
                    ),
                )

    def explode_flat(
        self,
        db: Session,
        parent_system_item_code: str,
        required_qty: float,
        version_id: int | None = None,
    ) -> list[dict]:
        on_date = datetime.utcnow().date()
        header = self._pick_header_by_parent_code(db, parent_system_item_code)
        if str(header.status).upper() != "ACTIVE":
            raise HTTPException(status_code=400, detail=f"BOM header is OBSOLETE for {parent_system_item_code}")

        version = self._pick_version_for_root(db, header, on_date, version_id)
        if str(version.status).upper() != "ACTIVE":
            raise HTTPException(status_code=400, detail="BOM version is not ACTIVE")

        flat: dict[str, _FlatLine] = {}
        self._explode_from_version(
            db=db,
            version=version,
            parent_required_qty=required_qty,
            on_date=on_date,
            path=[parent_system_item_code],
            flat=flat,
        )

        result = [
            {
                "item_code": row.item_code,
                "item_name": None,
                "total_qty": row.total_qty,
                "uom": row.uom,
            }
            for row in flat.values()
        ]
        result.sort(key=lambda x: x["item_code"])
        return result
