from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models import BOMHeader, BOMVersion, BOMLine
from app.schemas.bom_maintenance import (
    BOMHeaderCreate,
    BOMHeaderOut,
    BOMHeaderDetail,
    BOMVersionCreate,
    BOMVersionOut,
    BOMLineCreate,
    BOMLineOut,
)


router = APIRouter(prefix="/v2/bom-maintenance", tags=["v2-bom-maintenance"])
HEADER_ALLOWED_STATUS = {"ACTIVE", "OBSOLETE"}
VERSION_ALLOWED_STATUS = {"DRAFT", "ACTIVE", "OBSOLETE"}


def _is_active_without_approver(status: str, approved_by: str | None) -> bool:
    if status.strip().upper() != "ACTIVE":
        return False
    return not approved_by or not approved_by.strip()


@router.post("/headers", response_model=BOMHeaderOut)
def create_bom_header(payload: BOMHeaderCreate, db: Session = Depends(get_db)):
    header_status = payload.status.strip().upper()
    if header_status not in HEADER_ALLOWED_STATUS:
        raise HTTPException(status_code=400, detail="BOMHeader.status must be ACTIVE or OBSOLETE")

    row = BOMHeader(
        parent_system_item_code=payload.parent_system_item_code,
        bom_type=payload.bom_type,
        status=header_status,
        created_by=payload.created_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/headers", response_model=list[BOMHeaderOut])
def list_bom_headers(db: Session = Depends(get_db)):
    return db.query(BOMHeader).order_by(BOMHeader.bom_id.desc()).all()


@router.get("/headers/{bom_id}", response_model=BOMHeaderDetail)
def get_bom_header(bom_id: int, db: Session = Depends(get_db)):
    row = (
        db.query(BOMHeader)
        .options(selectinload(BOMHeader.versions).selectinload(BOMVersion.lines))
        .filter(BOMHeader.bom_id == bom_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="BOM header not found")
    return row


@router.post("/headers/{bom_id}/versions", response_model=BOMVersionOut)
def create_bom_version(bom_id: int, payload: BOMVersionCreate, db: Session = Depends(get_db)):
    header = db.query(BOMHeader).filter(BOMHeader.bom_id == bom_id).first()
    if not header:
        raise HTTPException(status_code=404, detail="BOM header not found")

    version_status = payload.status.strip().upper()
    if version_status not in VERSION_ALLOWED_STATUS:
        raise HTTPException(status_code=400, detail="BOMVersion.status must be DRAFT, ACTIVE, or OBSOLETE")

    if _is_active_without_approver(version_status, payload.approved_by):
        raise HTTPException(status_code=400, detail="ACTIVE version requires approved_by")

    if version_status == "ACTIVE":
        existing_active = (
            db.query(BOMVersion)
            .filter(BOMVersion.bom_id == bom_id)
            .filter(func.upper(BOMVersion.status) == "ACTIVE")
            .first()
        )
        if existing_active:
            raise HTTPException(status_code=400, detail="Only one ACTIVE version is allowed per bom_id")

    if payload.source_version_id is not None:
        source = db.query(BOMVersion).filter(BOMVersion.version_id == payload.source_version_id).first()
        if not source:
            raise HTTPException(status_code=400, detail="source_version_id not found")
        if source.bom_id != bom_id:
            raise HTTPException(status_code=400, detail="source_version_id must belong to the same bom_id")

    row = BOMVersion(
        bom_id=bom_id,
        bom_revision=payload.bom_revision,
        status=version_status,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        remarks=payload.remarks,
        created_by=payload.created_by,
        approved_by=payload.approved_by,
        approved_at=payload.approved_at,
        source_version_id=payload.source_version_id,
        change_trigger=payload.change_trigger,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/headers/{bom_id}/versions", response_model=list[BOMVersionOut])
def list_bom_versions(bom_id: int, db: Session = Depends(get_db)):
    header = db.query(BOMHeader).filter(BOMHeader.bom_id == bom_id).first()
    if not header:
        raise HTTPException(status_code=404, detail="BOM header not found")
    return (
        db.query(BOMVersion)
        .filter(BOMVersion.bom_id == bom_id)
        .order_by(BOMVersion.version_id.desc())
        .all()
    )


@router.get("/versions/{version_id}", response_model=BOMVersionOut)
def get_bom_version(version_id: int, db: Session = Depends(get_db)):
    row = db.query(BOMVersion).filter(BOMVersion.version_id == version_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="BOM version not found")
    return row


@router.post("/versions/{version_id}/lines", response_model=BOMLineOut)
def create_bom_line(version_id: int, payload: BOMLineCreate, db: Session = Depends(get_db)):
    version = db.query(BOMVersion).filter(BOMVersion.version_id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="BOM version not found")

    row = BOMLine(
        version_id=version_id,
        sequence=payload.sequence,
        component_system_item_code=payload.component_system_item_code,
        qty_per=payload.qty_per,
        uom=payload.uom,
        scrap_rate=payload.scrap_rate,
        phantom_flag=payload.phantom_flag,
        alt_group=payload.alt_group,
        alt_priority=payload.alt_priority,
        operation_id=payload.operation_id,
        notes=payload.notes,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/versions/{version_id}/lines", response_model=list[BOMLineOut])
def list_bom_lines(version_id: int, db: Session = Depends(get_db)):
    version = db.query(BOMVersion).filter(BOMVersion.version_id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="BOM version not found")
    return (
        db.query(BOMLine)
        .filter(BOMLine.version_id == version_id)
        .order_by(BOMLine.sequence.asc(), BOMLine.bom_line_id.asc())
        .all()
    )


@router.get("/lines/{bom_line_id}", response_model=BOMLineOut)
def get_bom_line(bom_line_id: int, db: Session = Depends(get_db)):
    row = db.query(BOMLine).filter(BOMLine.bom_line_id == bom_line_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="BOM line not found")
    return row
