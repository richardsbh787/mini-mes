from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.step47_phasea_declared_manual import (
    Step47PhaseADeclaredManualCorrection,
    Step47PhaseADeclaredManualCorrectionTraceRead,
    Step47PhaseADeclaredManualCreate,
    Step47PhaseADeclaredManualDetailRead,
    Step47PhaseADeclaredManualListResponse,
    Step47PhaseADeclaredManualSourceRead,
)
from models import (
    Step47PhaseADeclaredManualCorrectionTrace,
    Step47PhaseADeclaredManualSource,
)


def create_step47_phasea_declared_manual_source(
    db: Session,
    *,
    payload: Step47PhaseADeclaredManualCreate,
) -> Step47PhaseADeclaredManualSourceRead:
    row = Step47PhaseADeclaredManualSource(
        declared_by=payload.declared_by,
        declared_location=payload.declared_location,
        source_record_reference=payload.source_record_reference,
    )
    db.add(row)
    db.flush()
    return Step47PhaseADeclaredManualSourceRead.model_validate(row)


def correct_step47_phasea_declared_manual_source(
    db: Session,
    *,
    declaration_id: int,
    payload: Step47PhaseADeclaredManualCorrection,
) -> Step47PhaseADeclaredManualDetailRead:
    row = _load_declared_manual_source(db=db, declaration_id=declaration_id)

    next_declared_location = payload.declared_location or row.declared_location
    next_source_record_reference = payload.source_record_reference or row.source_record_reference
    location_changed = next_declared_location != row.declared_location
    reference_changed = next_source_record_reference != row.source_record_reference
    if not location_changed and not reference_changed:
        raise HTTPException(status_code=409, detail="correction must change at least one declared/manual field")

    trace = Step47PhaseADeclaredManualCorrectionTrace(
        declaration_id=row.id,
        corrected_by=payload.corrected_by,
        correction_reason=payload.correction_reason,
        previous_declared_location=row.declared_location if location_changed else None,
        new_declared_location=next_declared_location if location_changed else None,
        previous_source_record_reference=row.source_record_reference if reference_changed else None,
        new_source_record_reference=next_source_record_reference if reference_changed else None,
    )
    db.add(trace)

    row.declared_location = next_declared_location
    row.source_record_reference = next_source_record_reference
    db.add(row)
    db.flush()

    return get_step47_phasea_declared_manual_source_detail(db=db, declaration_id=declaration_id)


def get_step47_phasea_declared_manual_source_detail(
    db: Session,
    *,
    declaration_id: int,
) -> Step47PhaseADeclaredManualDetailRead:
    row = _load_declared_manual_source(db=db, declaration_id=declaration_id)
    traces = _list_correction_trace(db=db, declaration_id=declaration_id)
    return Step47PhaseADeclaredManualDetailRead(
        current_record=Step47PhaseADeclaredManualSourceRead.model_validate(row),
        original_record=_build_original_record(row=row, traces=traces),
        correction_trace=[Step47PhaseADeclaredManualCorrectionTraceRead.model_validate(trace) for trace in traces],
    )


def list_step47_phasea_declared_manual_sources_internal(
    db: Session,
) -> list[Step47PhaseADeclaredManualSourceRead]:
    rows = (
        db.query(Step47PhaseADeclaredManualSource)
        .order_by(Step47PhaseADeclaredManualSource.declared_at.desc(), Step47PhaseADeclaredManualSource.id.desc())
        .all()
    )
    return [Step47PhaseADeclaredManualSourceRead.model_validate(row) for row in rows]


def list_step47_phasea_declared_manual_source_read_surface(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
) -> Step47PhaseADeclaredManualListResponse:
    if page < 1:
        raise HTTPException(status_code=422, detail="page must be greater than or equal to 1")
    if page_size < 1 or page_size > 200:
        raise HTTPException(status_code=422, detail="page_size must be between 1 and 200")

    base_query = db.query(Step47PhaseADeclaredManualSource)
    total_count = base_query.count()
    rows = (
        base_query.order_by(
            Step47PhaseADeclaredManualSource.declared_at.desc(),
            Step47PhaseADeclaredManualSource.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return Step47PhaseADeclaredManualListResponse(
        items=[Step47PhaseADeclaredManualSourceRead.model_validate(row) for row in rows],
        page=page,
        page_size=page_size,
        total_count=total_count,
    )


def _build_original_record(
    *,
    row: Step47PhaseADeclaredManualSource,
    traces: list[Step47PhaseADeclaredManualCorrectionTrace],
) -> Step47PhaseADeclaredManualSourceRead:
    ordered_traces = sorted(
        traces,
        key=lambda trace: (
            trace.corrected_at,
            trace.id,
        ),
    )
    original_declared_location = row.declared_location
    original_source_record_reference = row.source_record_reference
    for trace in reversed(ordered_traces):
        if trace.previous_declared_location is not None:
            original_declared_location = trace.previous_declared_location
        if trace.previous_source_record_reference is not None:
            original_source_record_reference = trace.previous_source_record_reference
    return Step47PhaseADeclaredManualSourceRead(
        id=int(row.id),
        declared_by=str(row.declared_by or ""),
        declared_at=row.declared_at,
        declared_location=original_declared_location,
        source_record_reference=original_source_record_reference,
    )


def _load_declared_manual_source(
    *,
    db: Session,
    declaration_id: int,
) -> Step47PhaseADeclaredManualSource:
    row = (
        db.query(Step47PhaseADeclaredManualSource)
        .filter(Step47PhaseADeclaredManualSource.id == declaration_id)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Step 47 Phase A declared/manual source record not found")
    return row


def _list_correction_trace(
    *,
    db: Session,
    declaration_id: int,
) -> list[Step47PhaseADeclaredManualCorrectionTrace]:
    return (
        db.query(Step47PhaseADeclaredManualCorrectionTrace)
        .filter(Step47PhaseADeclaredManualCorrectionTrace.declaration_id == declaration_id)
        .order_by(
            Step47PhaseADeclaredManualCorrectionTrace.corrected_at.asc(),
            Step47PhaseADeclaredManualCorrectionTrace.id.asc(),
        )
        .all()
    )
