from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.schemas.step40a_daily_stock_audit import (
    DailyStockAuditFindingListQuery,
    DailyStockAuditFindingRead,
    DailyStockAuditManualTriggerRequest,
    DailyStockAuditRiskLevel,
    DailyStockAuditRuleCode,
    DailyStockAuditRunListQuery,
    DailyStockAuditRunRead,
    DailyStockAuditRunStatus,
    DailyStockAuditSchedulerEntryRead,
    DailyStockAuditTriggerSource,
    PhysicalCheckTaskListQuery,
    PhysicalCheckTaskRead,
    PhysicalCheckTaskStatus,
)
from app.models_step40a_daily_stock_audit import DailyStockAuditFinding, DailyStockAuditRun, PhysicalCheckTask
from database import SessionLocal
from models import StockLedger


SCHEDULER_JOB_NAME = "daily-smart-stock-check"
SCHEDULER_TIMEZONE = "Asia/Kuala_Lumpur"
SCHEDULER_CRON = "0 0 * * *"
HIGH_MOVEMENT_DENSITY_THRESHOLD = 4
EXCESSIVE_CORRECTION_ACTIVITY_THRESHOLD = 2
HIGH_RISK_THRESHOLD = 50

RULE_SCORES = {
    DailyStockAuditRuleCode.R01_NEGATIVE_BALANCE: 50,
    DailyStockAuditRuleCode.R02_HIGH_MOVEMENT_DENSITY: 20,
    DailyStockAuditRuleCode.R03_SAME_DAY_IN_OUT_OSCILLATION: 20,
    DailyStockAuditRuleCode.R04_EXCESSIVE_CORRECTION_ACTIVITY: 30,
    DailyStockAuditRuleCode.R05_BUCKET_FLOW_ABNORMALITY: 20,
}


@dataclass
class _CandidateAuditState:
    org_id: str
    item_code: str
    item_id: str | None
    audit_date: date
    primary_stock_bucket: str | None
    movement_count: int
    correction_count: int
    net_balance_qty: float
    distinct_bucket_count: int
    triggered_rules: list[DailyStockAuditRuleCode]
    risk_score: int
    risk_level: DailyStockAuditRiskLevel
    suspicious_summary: str


def build_daily_stock_audit_scheduler_entry() -> DailyStockAuditSchedulerEntryRead:
    return DailyStockAuditSchedulerEntryRead(
        job_name=SCHEDULER_JOB_NAME,
        cron=SCHEDULER_CRON,
        timezone=SCHEDULER_TIMEZONE,
        enabled=True,
    )


def run_daily_stock_audit(
    db: Session,
    *,
    trigger_source: DailyStockAuditTriggerSource,
    payload: DailyStockAuditManualTriggerRequest | None = None,
    audit_date: date | None = None,
    scheduler_entry_name: str | None = None,
    scheduler_timezone: str | None = None,
) -> DailyStockAuditRunRead:
    try:
        # Guard 01: input / schedule date validation
        normalized_audit_date = _resolve_audit_date(payload=payload, audit_date=audit_date)

        # Guard 02: duplicate run-date success guard
        existing = (
            db.query(DailyStockAuditRun)
            .filter(DailyStockAuditRun.audit_date == normalized_audit_date)
            .filter(DailyStockAuditRun.status == DailyStockAuditRunStatus.SUCCESS.value)
            .first()
        )
        if existing is not None:
            raise HTTPException(status_code=409, detail="daily stock audit already completed successfully for audit_date")

        # Guard 03: ledger source availability guard
        _assert_ledger_source_available(db)

        run_row = DailyStockAuditRun(
            run_no=_next_no(prefix="DSAR"),
            audit_date=normalized_audit_date,
            trigger_source=trigger_source.value,
            scheduler_timezone=scheduler_timezone,
            scheduler_entry_name=scheduler_entry_name,
            status=DailyStockAuditRunStatus.SUCCESS.value,
            candidate_item_count=0,
            finding_count=0,
            physical_check_task_count=0,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db.add(run_row)
        db.flush()

        # Guard 04: candidate item selection
        candidates = _select_candidate_items(db=db, audit_date=normalized_audit_date)
        run_row.candidate_item_count = len(candidates)

        finding_count = 0
        physical_check_task_count = 0

        for candidate_rows in candidates:
            # Guard 05: per-item audit rule evaluation
            state = _evaluate_candidate(candidate_rows=candidate_rows, audit_date=normalized_audit_date)
            if not state.triggered_rules:
                continue

            # Guard 06: finding write
            finding_row = DailyStockAuditFinding(
                run_id=run_row.id,
                org_id=state.org_id,
                item_id=state.item_id,
                item_code=state.item_code,
                primary_stock_bucket=state.primary_stock_bucket,
                audit_date=state.audit_date,
                triggered_rule_codes=",".join(rule.value for rule in state.triggered_rules),
                risk_score=state.risk_score,
                risk_level=state.risk_level.value,
                movement_count=state.movement_count,
                correction_count=state.correction_count,
                net_balance_qty=state.net_balance_qty,
                distinct_bucket_count=state.distinct_bucket_count,
                suspicious_summary=state.suspicious_summary,
                created_at=datetime.utcnow(),
            )
            db.add(finding_row)
            db.flush()
            finding_count += 1

            # Guard 07: physical-check task decision
            if _should_create_physical_check_task(state):
                task_row = PhysicalCheckTask(
                    task_no=_next_no(prefix="PCT"),
                    run_id=run_row.id,
                    finding_id=finding_row.id,
                    org_id=state.org_id,
                    item_code=state.item_code,
                    status=PhysicalCheckTaskStatus.OPEN.value,
                    priority=state.risk_level.value,
                    reason_code=_physical_check_reason_code(state),
                    created_at=datetime.utcnow(),
                )
                db.add(task_row)
                physical_check_task_count += 1

        # Guard 08: run summary finalize
        run_row.finding_count = finding_count
        run_row.physical_check_task_count = physical_check_task_count
        run_row.completed_at = datetime.utcnow()
        db.flush()
        db.commit()
        db.refresh(run_row)
        return DailyStockAuditRunRead.model_validate(run_row)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="daily stock audit execution failed")


def list_daily_stock_audit_runs(
    db: Session,
    *,
    query: DailyStockAuditRunListQuery,
) -> list[DailyStockAuditRunRead]:
    rows_query = db.query(DailyStockAuditRun)
    if query.audit_date_from is not None:
        rows_query = rows_query.filter(DailyStockAuditRun.audit_date >= query.audit_date_from)
    if query.audit_date_to is not None:
        rows_query = rows_query.filter(DailyStockAuditRun.audit_date <= query.audit_date_to)
    if query.status is not None:
        rows_query = rows_query.filter(DailyStockAuditRun.status == query.status.value)
    if query.trigger_source is not None:
        rows_query = rows_query.filter(DailyStockAuditRun.trigger_source == query.trigger_source.value)
    rows = (
        rows_query
        .order_by(DailyStockAuditRun.audit_date.desc(), DailyStockAuditRun.id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
        .all()
    )
    return [DailyStockAuditRunRead.model_validate(row) for row in rows]


def list_daily_stock_audit_findings(
    db: Session,
    *,
    query: DailyStockAuditFindingListQuery,
) -> list[DailyStockAuditFindingRead]:
    rows_query = db.query(DailyStockAuditFinding)
    if query.run_id is not None:
        rows_query = rows_query.filter(DailyStockAuditFinding.run_id == query.run_id)
    if query.audit_date_from is not None:
        rows_query = rows_query.filter(DailyStockAuditFinding.audit_date >= query.audit_date_from)
    if query.audit_date_to is not None:
        rows_query = rows_query.filter(DailyStockAuditFinding.audit_date <= query.audit_date_to)
    if query.risk_level is not None:
        rows_query = rows_query.filter(DailyStockAuditFinding.risk_level == query.risk_level.value)
    if query.rule_code is not None:
        rows_query = rows_query.filter(DailyStockAuditFinding.triggered_rule_codes.like(f"%{query.rule_code.value}%"))
    if query.item_code is not None:
        rows_query = rows_query.filter(DailyStockAuditFinding.item_code == query.item_code)
    if query.org_id is not None:
        rows_query = rows_query.filter(DailyStockAuditFinding.org_id == query.org_id)
    rows = (
        rows_query
        .order_by(DailyStockAuditFinding.audit_date.desc(), DailyStockAuditFinding.id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
        .all()
    )
    return [DailyStockAuditFindingRead.model_validate(row) for row in rows]


def list_physical_check_tasks(
    db: Session,
    *,
    query: PhysicalCheckTaskListQuery,
) -> list[PhysicalCheckTaskRead]:
    rows_query = db.query(PhysicalCheckTask)
    if query.run_id is not None:
        rows_query = rows_query.filter(PhysicalCheckTask.run_id == query.run_id)
    if query.status is not None:
        rows_query = rows_query.filter(PhysicalCheckTask.status == query.status.value)
    if query.item_code is not None:
        rows_query = rows_query.filter(PhysicalCheckTask.item_code == query.item_code)
    if query.org_id is not None:
        rows_query = rows_query.filter(PhysicalCheckTask.org_id == query.org_id)
    rows = (
        rows_query
        .order_by(PhysicalCheckTask.created_at.desc(), PhysicalCheckTask.id.desc())
        .offset((query.page - 1) * query.page_size)
        .limit(query.page_size)
        .all()
    )
    return [PhysicalCheckTaskRead.model_validate(row) for row in rows]


def register_daily_stock_audit_scheduler(app: FastAPI) -> None:
    app.state.daily_stock_audit_scheduler_entry = build_daily_stock_audit_scheduler_entry()

    @app.on_event("startup")
    async def _daily_stock_audit_startup() -> None:
        if getattr(app.state, "daily_stock_audit_scheduler_task", None) is None:
            app.state.daily_stock_audit_scheduler_task = asyncio.create_task(_daily_stock_audit_loop())

    @app.on_event("shutdown")
    async def _daily_stock_audit_shutdown() -> None:
        task = getattr(app.state, "daily_stock_audit_scheduler_task", None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            app.state.daily_stock_audit_scheduler_task = None


async def _daily_stock_audit_loop() -> None:
    timezone = ZoneInfo(SCHEDULER_TIMEZONE)
    while True:
        now = datetime.now(timezone)
        next_run = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=timezone)
        wait_seconds = max((next_run - now).total_seconds(), 1.0)
        await asyncio.sleep(wait_seconds)
        db = SessionLocal()
        try:
            run_daily_stock_audit(
                db,
                trigger_source=DailyStockAuditTriggerSource.SCHEDULED,
                audit_date=datetime.now(timezone).date(),
                scheduler_entry_name=SCHEDULER_JOB_NAME,
                scheduler_timezone=SCHEDULER_TIMEZONE,
            )
        except HTTPException as exc:
            if exc.status_code != 409:
                raise
        finally:
            db.close()


def _resolve_audit_date(
    *,
    payload: DailyStockAuditManualTriggerRequest | None,
    audit_date: date | None,
) -> date:
    if audit_date is not None:
        return audit_date
    if payload is not None and payload.audit_date is not None:
        return payload.audit_date
    return datetime.now(ZoneInfo(SCHEDULER_TIMEZONE)).date()


def _assert_ledger_source_available(db: Session) -> None:
    try:
        db.query(StockLedger.id).limit(1).all()
    except Exception as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=503, detail="stock ledger source unavailable") from exc


def _select_candidate_items(
    *,
    db: Session,
    audit_date: date,
) -> list[list[StockLedger]]:
    rows = db.query(StockLedger).order_by(StockLedger.posted_at.asc(), StockLedger.occurred_at.asc(), StockLedger.id.asc()).all()
    grouped: dict[tuple[str, str], list[StockLedger]] = defaultdict(list)
    for row in rows:
        row_date = _posted_at(row).date()
        if row_date != audit_date:
            continue
        grouped[(str(row.org_id or "").strip(), _item_code(row))].append(row)
    return list(grouped.values())


def _evaluate_candidate(
    *,
    candidate_rows: list[StockLedger],
    audit_date: date,
) -> _CandidateAuditState:
    first_row = candidate_rows[0]
    org_id = str(first_row.org_id or "").strip()
    item_code = _item_code(first_row)
    item_id = str(first_row.item_id or "").strip() or None
    stock_buckets = {_normalize_optional(row.stock_bucket, upper=True) for row in candidate_rows if _normalize_optional(row.stock_bucket, upper=True)}
    movement_types = [_movement_type(row) for row in candidate_rows]
    correction_count = sum(1 for row in candidate_rows if _is_correction(row))
    net_balance_qty = sum(_signed_base_qty(row) for row in candidate_rows)
    triggered_rules: list[DailyStockAuditRuleCode] = []

    if net_balance_qty < 0:
        triggered_rules.append(DailyStockAuditRuleCode.R01_NEGATIVE_BALANCE)
    if len(candidate_rows) >= HIGH_MOVEMENT_DENSITY_THRESHOLD:
        triggered_rules.append(DailyStockAuditRuleCode.R02_HIGH_MOVEMENT_DENSITY)
    if "IN" in movement_types and "OUT" in movement_types:
        triggered_rules.append(DailyStockAuditRuleCode.R03_SAME_DAY_IN_OUT_OSCILLATION)
    if correction_count >= EXCESSIVE_CORRECTION_ACTIVITY_THRESHOLD:
        triggered_rules.append(DailyStockAuditRuleCode.R04_EXCESSIVE_CORRECTION_ACTIVITY)
    if len(stock_buckets) >= 2:
        triggered_rules.append(DailyStockAuditRuleCode.R05_BUCKET_FLOW_ABNORMALITY)

    risk_score = sum(RULE_SCORES[rule] for rule in triggered_rules)
    risk_level = _risk_level_for_score(risk_score)
    primary_stock_bucket = sorted(stock_buckets)[0] if len(stock_buckets) == 1 else "MIXED" if stock_buckets else None
    suspicious_summary = _build_summary(
        item_code=item_code,
        movement_count=len(candidate_rows),
        correction_count=correction_count,
        net_balance_qty=net_balance_qty,
        distinct_bucket_count=len(stock_buckets),
        triggered_rules=triggered_rules,
    )
    return _CandidateAuditState(
        org_id=org_id,
        item_code=item_code,
        item_id=item_id,
        audit_date=audit_date,
        primary_stock_bucket=primary_stock_bucket,
        movement_count=len(candidate_rows),
        correction_count=correction_count,
        net_balance_qty=net_balance_qty,
        distinct_bucket_count=len(stock_buckets),
        triggered_rules=triggered_rules,
        risk_score=risk_score,
        risk_level=risk_level,
        suspicious_summary=suspicious_summary,
    )


def _risk_level_for_score(score: int) -> DailyStockAuditRiskLevel:
    if score >= HIGH_RISK_THRESHOLD:
        return DailyStockAuditRiskLevel.HIGH
    if score >= 20:
        return DailyStockAuditRiskLevel.MEDIUM
    return DailyStockAuditRiskLevel.LOW


def _build_summary(
    *,
    item_code: str,
    movement_count: int,
    correction_count: int,
    net_balance_qty: float,
    distinct_bucket_count: int,
    triggered_rules: list[DailyStockAuditRuleCode],
) -> str:
    return (
        f"item={item_code}; movements={movement_count}; corrections={correction_count}; "
        f"net_balance_qty={net_balance_qty:.2f}; distinct_buckets={distinct_bucket_count}; "
        f"rules={','.join(rule.value for rule in triggered_rules)}"
    )


def _should_create_physical_check_task(state: _CandidateAuditState) -> bool:
    return (
        DailyStockAuditRuleCode.R01_NEGATIVE_BALANCE in state.triggered_rules
        or state.risk_level == DailyStockAuditRiskLevel.HIGH
    )


def _physical_check_reason_code(state: _CandidateAuditState) -> str:
    if DailyStockAuditRuleCode.R01_NEGATIVE_BALANCE in state.triggered_rules:
        return DailyStockAuditRuleCode.R01_NEGATIVE_BALANCE.value
    return "HIGH_RISK_MOVEMENT_HEALTH"


def _item_code(row: StockLedger) -> str:
    return str(row.item_code or row.item_id or "").strip().upper()


def _movement_type(row: StockLedger) -> str:
    return str(row.movement_type or "").strip().upper()


def _normalize_optional(value: str | None, *, upper: bool = False) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized.upper() if upper else normalized


def _base_qty(row: StockLedger) -> float:
    if row.base_qty is not None:
        return abs(float(row.base_qty))
    return abs(float(row.qty or 0))


def _signed_base_qty(row: StockLedger) -> float:
    movement_type = _movement_type(row)
    qty = _base_qty(row)
    if movement_type == "OUT":
        return -qty
    if movement_type == "IN":
        return qty
    return float(row.qty or 0)


def _posted_at(row: StockLedger) -> datetime:
    return row.posted_at or row.occurred_at or datetime.min


def _is_correction(row: StockLedger) -> bool:
    signals = [
        str(row.txn_type or "").upper(),
        str(row.source_event_type or "").upper(),
        str(row.note or "").upper(),
        str(row.remark or "").upper(),
    ]
    return any("ADJ" in signal or "CORRECTION" in signal for signal in signals)


def _next_no(*, prefix: str) -> str:
    return f"{prefix}-{datetime.utcnow():%Y%m%d%H%M%S}-{uuid4().hex[:8].upper()}"
