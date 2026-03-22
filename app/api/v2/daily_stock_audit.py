from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.step40a_daily_stock_audit import (
    DailyStockAuditFindingRead,
    DailyStockAuditManualTriggerRequest,
    DailyStockAuditRiskLevel,
    DailyStockAuditRuleCode,
    DailyStockAuditRunRead,
    DailyStockAuditRunStatus,
    DailyStockAuditSchedulerEntryRead,
    DailyStockAuditTriggerSource,
    PhysicalCheckTaskRead,
    PhysicalCheckTaskStatus,
)
from app.schemas.step40a_daily_stock_audit import (
    DailyStockAuditFindingListQuery,
    DailyStockAuditRunListQuery,
    PhysicalCheckTaskListQuery,
)
from app.services.step40a_daily_stock_audit import (
    build_daily_stock_audit_scheduler_entry,
    list_daily_stock_audit_findings,
    list_daily_stock_audit_runs,
    list_physical_check_tasks,
    run_daily_stock_audit,
)
from database import get_db


router = APIRouter(prefix="/v2/daily-stock-audit", tags=["v2-daily-stock-audit"])


@router.get("/scheduler", response_model=DailyStockAuditSchedulerEntryRead)
def daily_stock_audit_scheduler() -> DailyStockAuditSchedulerEntryRead:
    return build_daily_stock_audit_scheduler_entry()


@router.post("/runs/trigger", response_model=DailyStockAuditRunRead)
def daily_stock_audit_manual_trigger(
    payload: DailyStockAuditManualTriggerRequest,
    db: Session = Depends(get_db),
) -> DailyStockAuditRunRead:
    return run_daily_stock_audit(
        db,
        trigger_source=DailyStockAuditTriggerSource.MANUAL,
        payload=payload,
    )


@router.get("/runs", response_model=list[DailyStockAuditRunRead])
def daily_stock_audit_run_list(
    audit_date_from: date | None = None,
    audit_date_to: date | None = None,
    status: DailyStockAuditRunStatus | None = None,
    trigger_source: DailyStockAuditTriggerSource | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
) -> list[DailyStockAuditRunRead]:
    return list_daily_stock_audit_runs(
        db,
        query=DailyStockAuditRunListQuery(
            audit_date_from=audit_date_from,
            audit_date_to=audit_date_to,
            status=status,
            trigger_source=trigger_source,
            page=page,
            page_size=page_size,
        ),
    )


@router.get("/findings", response_model=list[DailyStockAuditFindingRead])
def daily_stock_audit_finding_list(
    run_id: int | None = None,
    audit_date_from: date | None = None,
    audit_date_to: date | None = None,
    risk_level: DailyStockAuditRiskLevel | None = None,
    rule_code: DailyStockAuditRuleCode | None = None,
    item_code: str | None = None,
    org_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
) -> list[DailyStockAuditFindingRead]:
    return list_daily_stock_audit_findings(
        db,
        query=DailyStockAuditFindingListQuery(
            run_id=run_id,
            audit_date_from=audit_date_from,
            audit_date_to=audit_date_to,
            risk_level=risk_level,
            rule_code=rule_code,
            item_code=item_code,
            org_id=org_id,
            page=page,
            page_size=page_size,
        ),
    )


@router.get("/physical-check-tasks", response_model=list[PhysicalCheckTaskRead])
def daily_stock_audit_physical_check_task_list(
    run_id: int | None = None,
    status: PhysicalCheckTaskStatus | None = None,
    item_code: str | None = None,
    org_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
) -> list[PhysicalCheckTaskRead]:
    return list_physical_check_tasks(
        db,
        query=PhysicalCheckTaskListQuery(
            run_id=run_id,
            status=status,
            item_code=item_code,
            org_id=org_id,
            page=page,
            page_size=page_size,
        ),
    )
