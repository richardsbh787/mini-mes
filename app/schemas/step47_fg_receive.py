from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class FgReceiveResolutionOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"


class FgReceiveStep47ExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    executed_by: str = Field(min_length=1)
    remark: str | None = None


class FgReceiveStep47ExecuteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fg_receive_id: int
    attempt_id: int
    outcome_class: FgReceiveResolutionOutcome
    evidence_snapshot_id: int | None = None
    final_truth_id: int | None = None
    stock_ledger_id: int | None = None
    bound_location_code: str | None = None
    admitted_source_activation_active: bool
    runtime_production_use_authorized: bool


class FgReceiveResolutionListItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fg_receive_id: int
    fg_receive_no: str
    work_order_id: int
    latest_outcome_class: FgReceiveResolutionOutcome | None = None
    has_final_truth: bool
    has_evidence_snapshot: bool
    has_attempt_linkage: bool
    has_evidence_linkage: bool
    has_final_truth_linkage: bool
    fg_receive_received_at: datetime
    attempt_attempted_at: datetime | None = None
    evidence_captured_at: datetime | None = None
    final_truth_bound_at: datetime | None = None


class FgReceiveSourceEventContextRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    fg_receive_id: int
    fg_receive_no: str
    work_order_id: int
    wip_transfer_id: int
    routing_snapshot_id: int
    fg_handling_unit_type: str
    fg_handling_unit_label: str | None = None
    txn_qty: float
    txn_uom: str
    receive_status: str
    received_at: datetime
    received_by: str
    remark: str | None = None


class FgReceiveAttemptRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    attempt_id: int
    source_label_token: str | None = None
    outcome_class: FgReceiveResolutionOutcome
    resolved_location_code: str | None = None
    failure_reason: str | None = None
    evidence_snapshot_id: int | None = None
    attempted_at: datetime
    completed_at: datetime | None = None
    attempted_by: str


class FgReceiveEvidenceSnapshotRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_snapshot_id: int
    source_label_token: str | None = None
    label_type: str | None = None
    location_label_id: int | None = None
    label_status: str | None = None
    label_matched: bool
    matched_mapping_id: int | None = None
    mapping_status: str | None = None
    matched_location_id: int | None = None
    matched_location_code: str | None = None
    matched_location_status: str | None = None
    mapping_effective_from: datetime | None = None
    mapping_effective_to: datetime | None = None
    event_received_at: datetime
    captured_at: datetime
    evidence_source: str
    failure_reason: str | None = None


class FgReceiveRuntimeOutcomeRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    latest_outcome_class: FgReceiveResolutionOutcome | None = None
    latest_attempt_id: int | None = None
    latest_attempted_at: datetime | None = None
    latest_completed_at: datetime | None = None
    latest_failure_reason: str | None = None


class FgReceiveFinalTruthRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    final_truth_id: int
    bound_location_code: str
    bound_from_resolution_attempt_id: int
    location_evidence_snapshot_ref: int
    location_bound_at: datetime


class FgReceiveResolutionDetailRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_event_context: FgReceiveSourceEventContextRead
    attempt_history: list[FgReceiveAttemptRead]
    evidence_snapshots: list[FgReceiveEvidenceSnapshotRead]
    runtime_outcome: FgReceiveRuntimeOutcomeRead
    final_event_truth: FgReceiveFinalTruthRead | None = None


class FgReceiveResolutionSummaryRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    success_count: int
    failed_count: int
    ambiguous_count: int
    unresolved_count: int
    with_final_truth_count: int
    without_final_truth_count: int
    with_evidence_snapshot_count: int
    without_evidence_snapshot_count: int
