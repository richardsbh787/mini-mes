from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


MIN_PAGE_SIZE = 1
MAX_PAGE_SIZE = 100


class DailyStockAuditRunStatus(str, Enum):
    SUCCESS = "SUCCESS"


class DailyStockAuditTriggerSource(str, Enum):
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"


class DailyStockAuditRuleCode(str, Enum):
    R01_NEGATIVE_BALANCE = "R01_NEGATIVE_BALANCE"
    R02_HIGH_MOVEMENT_DENSITY = "R02_HIGH_MOVEMENT_DENSITY"
    R03_SAME_DAY_IN_OUT_OSCILLATION = "R03_SAME_DAY_IN_OUT_OSCILLATION"
    R04_EXCESSIVE_CORRECTION_ACTIVITY = "R04_EXCESSIVE_CORRECTION_ACTIVITY"
    R05_BUCKET_FLOW_ABNORMALITY = "R05_BUCKET_FLOW_ABNORMALITY"


class DailyStockAuditRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PhysicalCheckTaskStatus(str, Enum):
    OPEN = "OPEN"


class DailyStockAuditSchedulerEntryRead(BaseModel):
    job_name: str
    cron: str
    timezone: str
    enabled: bool = True


class DailyStockAuditManualTriggerRequest(BaseModel):
    audit_date: date | None = None


class DailyStockAuditRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_no: str
    audit_date: date
    trigger_source: str
    scheduler_timezone: str | None = None
    scheduler_entry_name: str | None = None
    status: str
    candidate_item_count: int
    finding_count: int
    physical_check_task_count: int
    started_at: datetime
    completed_at: datetime


class DailyStockAuditFindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    org_id: str
    item_id: str | None = None
    item_code: str
    primary_stock_bucket: str | None = None
    audit_date: date
    triggered_rule_codes: str
    risk_score: int
    risk_level: str
    movement_count: int
    correction_count: int
    net_balance_qty: float
    distinct_bucket_count: int
    suspicious_summary: str
    created_at: datetime


class PhysicalCheckTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_no: str
    run_id: int
    finding_id: int
    org_id: str
    item_code: str
    status: str
    priority: str
    reason_code: str
    created_at: datetime


class DailyStockAuditRunListQuery(BaseModel):
    audit_date_from: date | None = None
    audit_date_to: date | None = None
    status: DailyStockAuditRunStatus | None = None
    trigger_source: DailyStockAuditTriggerSource | None = None
    page: int = Field(default=1)
    page_size: int = Field(default=20)

    @model_validator(mode="after")
    def validate_filters(self) -> "DailyStockAuditRunListQuery":
        _validate_date_range(self.audit_date_from, self.audit_date_to)
        _validate_pagination(self.page, self.page_size)
        return self


class DailyStockAuditFindingListQuery(BaseModel):
    run_id: int | None = None
    audit_date_from: date | None = None
    audit_date_to: date | None = None
    risk_level: DailyStockAuditRiskLevel | None = None
    rule_code: DailyStockAuditRuleCode | None = None
    item_code: str | None = None
    org_id: str | None = None
    page: int = Field(default=1)
    page_size: int = Field(default=20)

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "DailyStockAuditFindingListQuery":
        self.item_code = _normalize_optional(self.item_code, upper=True)
        self.org_id = _normalize_optional(self.org_id)
        _validate_date_range(self.audit_date_from, self.audit_date_to)
        _validate_pagination(self.page, self.page_size)
        return self


class PhysicalCheckTaskListQuery(BaseModel):
    run_id: int | None = None
    status: PhysicalCheckTaskStatus | None = None
    item_code: str | None = None
    org_id: str | None = None
    page: int = Field(default=1)
    page_size: int = Field(default=20)

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "PhysicalCheckTaskListQuery":
        self.item_code = _normalize_optional(self.item_code, upper=True)
        self.org_id = _normalize_optional(self.org_id)
        _validate_pagination(self.page, self.page_size)
        return self


def _normalize_optional(value: str | None, *, upper: bool = False) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    return normalized.upper() if upper else normalized


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise ValueError("audit_date_from must be on or before audit_date_to")


def _validate_pagination(page: int, page_size: int) -> None:
    if page < 1:
        raise ValueError("page must be greater than or equal to 1")
    if page_size < MIN_PAGE_SIZE or page_size > MAX_PAGE_SIZE:
        raise ValueError(f"page_size must be between {MIN_PAGE_SIZE} and {MAX_PAGE_SIZE}")
