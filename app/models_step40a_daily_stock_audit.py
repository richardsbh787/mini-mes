from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String

from database import Base


class DailyStockAuditRun(Base):
    __tablename__ = "daily_stock_audit_run"

    id = Column(Integer, primary_key=True, index=True)
    run_no = Column(String, nullable=False, unique=True, index=True)
    audit_date = Column(Date, nullable=False, index=True)
    trigger_source = Column(String, nullable=False, index=True)
    scheduler_timezone = Column(String, nullable=True)
    scheduler_entry_name = Column(String, nullable=True)
    status = Column(String, nullable=False, index=True)
    candidate_item_count = Column(Integer, nullable=False, default=0)
    finding_count = Column(Integer, nullable=False, default=0)
    physical_check_task_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class DailyStockAuditFinding(Base):
    __tablename__ = "daily_stock_audit_finding"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("daily_stock_audit_run.id"), nullable=False, index=True)
    org_id = Column(String, nullable=False, index=True)
    item_id = Column(String, nullable=True, index=True)
    item_code = Column(String, nullable=False, index=True)
    primary_stock_bucket = Column(String, nullable=True, index=True)
    audit_date = Column(Date, nullable=False, index=True)
    triggered_rule_codes = Column(String, nullable=False)
    risk_score = Column(Integer, nullable=False, default=0)
    risk_level = Column(String, nullable=False, index=True)
    movement_count = Column(Integer, nullable=False, default=0)
    correction_count = Column(Integer, nullable=False, default=0)
    net_balance_qty = Column(Float, nullable=False, default=0)
    distinct_bucket_count = Column(Integer, nullable=False, default=0)
    suspicious_summary = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class PhysicalCheckTask(Base):
    __tablename__ = "physical_check_task"

    id = Column(Integer, primary_key=True, index=True)
    task_no = Column(String, nullable=False, unique=True, index=True)
    run_id = Column(Integer, ForeignKey("daily_stock_audit_run.id"), nullable=False, index=True)
    finding_id = Column(Integer, ForeignKey("daily_stock_audit_finding.id"), nullable=False, index=True)
    org_id = Column(String, nullable=False, index=True)
    item_code = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="OPEN", index=True)
    priority = Column(String, nullable=False, default="HIGH", index=True)
    reason_code = Column(String, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
