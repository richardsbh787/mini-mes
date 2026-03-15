from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import BOMLine, BOMVersion
from app.services.bom_flat_explosion_service import BOMFlatExplosionService


class BOMTreeExplosionService:
    def __init__(self):
        # Reuse Step 3 root/header/version validation rules.
        self.flat_rules = BOMFlatExplosionService()

    def _build_children(
        self,
        db: Session,
        version: BOMVersion,
        parent_required_qty: float,
        level: int,
        path: list[str],
        on_date,
    ) -> list[dict]:
        lines = (
            db.query(BOMLine)
            .filter(BOMLine.version_id == version.version_id)
            .order_by(BOMLine.sequence.asc(), BOMLine.bom_line_id.asc())
            .all()
        )

        children: list[dict] = []
        for line in lines:
            child_code = line.component_system_item_code
            if child_code in path:
                cycle_path = " -> ".join(path + [child_code])
                raise HTTPException(status_code=400, detail=f"Cycle detected: {cycle_path}")

            child_required_qty = parent_required_qty * float(line.qty_per) * (1 + float(line.scrap_rate))
            child_path = path + [child_code]

            child_target = self.flat_rules._try_pick_child_header_and_version(db, child_code, on_date)
            grand_children: list[dict] = []
            if child_target:
                _, child_version = child_target
                grand_children = self._build_children(
                    db=db,
                    version=child_version,
                    parent_required_qty=child_required_qty,
                    level=level + 1,
                    path=child_path,
                    on_date=on_date,
                )

            children.append(
                {
                    "item_code": child_code,
                    "item_name": self.flat_rules._lookup_item_name(db, child_code),
                    "required_qty": child_required_qty,
                    "uom": line.uom,
                    "level": level + 1,
                    "path": child_path,
                    "is_phantom": bool(line.phantom_flag),
                    "is_leaf": len(grand_children) == 0,
                    "children": grand_children,
                }
            )

        return children

    def explode_tree(
        self,
        db: Session,
        parent_system_item_code: str,
        required_qty: float,
        version_id: int | None = None,
    ) -> dict:
        on_date = datetime.now(timezone.utc).date()
        header = self.flat_rules._pick_header_by_parent_code(db, parent_system_item_code)
        version = self.flat_rules._pick_version_for_root(db, header, on_date, version_id)

        if str(header.status).upper() != "ACTIVE":
            raise HTTPException(status_code=400, detail=f"BOM header is OBSOLETE for {parent_system_item_code}")
        if str(version.status).upper() != "ACTIVE":
            raise HTTPException(status_code=400, detail="BOM version is not ACTIVE")

        children = self._build_children(
            db=db,
            version=version,
            parent_required_qty=required_qty,
            level=0,
            path=[parent_system_item_code],
            on_date=on_date,
        )

        return {
            "root_item_code": parent_system_item_code,
            "version_id": version.version_id,
            "tree": {
                "item_code": parent_system_item_code,
                "item_name": self.flat_rules._lookup_item_name(db, parent_system_item_code),
                "required_qty": required_qty,
                "uom": None,
                "level": 0,
                "path": [parent_system_item_code],
                "is_phantom": False,
                "is_leaf": len(children) == 0,
                "children": children,
            },
        }
