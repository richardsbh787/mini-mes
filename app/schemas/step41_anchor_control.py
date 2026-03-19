from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProcessContext(str, Enum):
    PP = "PP"
    ASSY = "ASSY"
    PACKING = "PACKING"


class ManualFallbackReasonCode(str, Enum):
    PRINTER_FAILURE = "PRINTER_FAILURE"
    SCANNER_FAILURE = "SCANNER_FAILURE"
    DAMAGED_UNREADABLE_LABEL = "DAMAGED_UNREADABLE_LABEL"
    CUSTOMER_TEMP_NO_SCAN = "CUSTOMER_TEMP_NO_SCAN"
    APPROVED_TEMP_FALLBACK_RUN = "APPROVED_TEMP_FALLBACK_RUN"


class PackingDetailInput(BaseModel):
    process_context: ProcessContext
    label_type: str = Field(min_length=1)
    pack_unit_qty: float = Field(gt=0)
    allow_partial: bool = False

    @model_validator(mode="after")
    def normalize_fields(self) -> "PackingDetailInput":
        self.label_type = str(self.label_type or "").strip().upper()
        return self


class PackingDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int
    process_context: str
    label_type: str
    basis_qty: float
    pack_unit_qty: float
    full_pack_count: int
    partial_pack_qty: float
    expected_label_qty: int
    printed_label_qty: int
    remaining_printable_qty: int
    allow_partial: bool


class ExpectedPrintPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    work_order_id: int
    anchor_type: str
    label_type: str
    process_context: str
    basis_qty: float
    expected_label_qty: int
    printed_label_qty: int
    remaining_printable_qty: int
    calculated_at: datetime


class LabelRangeBatchCreate(BaseModel):
    range_batch_id: str = Field(min_length=1)
    work_order_id: int
    anchor_type: str = Field(min_length=1)
    range_start_no: int = Field(gt=0)
    range_last_no: int = Field(gt=0)
    planned_qty: int = Field(ge=0)
    issued_by: str = Field(min_length=1)
    issued_at: datetime

    @model_validator(mode="after")
    def normalize_fields(self) -> "LabelRangeBatchCreate":
        self.range_batch_id = str(self.range_batch_id or "").strip().upper()
        self.anchor_type = str(self.anchor_type or "").strip().upper()
        self.issued_by = str(self.issued_by or "").strip()
        if self.range_last_no < self.range_start_no:
            raise ValueError("range_last_no must be greater than or equal to range_start_no")
        return self


class LabelRangeBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    range_batch_id: str
    work_order_id: int
    anchor_type: str
    range_start_no: int
    range_last_no: int
    range_qty: int
    planned_qty: int
    issued_qty: int
    printed_qty: int
    issued_to_line_qty: int
    used_qty: int
    damaged_qty: int
    void_qty: int
    unused_qty: int
    issued_by: str
    issued_at: datetime
    status: str


class LabelInstanceCreate(BaseModel):
    anchor_type: str = Field(min_length=1)
    anchor_value: str = Field(min_length=1)
    work_order_id: int
    run_seq_no: int = Field(gt=0)
    range_batch_id: str = Field(min_length=1)
    printed_by: str = Field(min_length=1)
    printed_at: datetime
    replaced_from_label_id: int | None = None
    reprint_reason: str | None = None

    @model_validator(mode="after")
    def normalize_fields(self) -> "LabelInstanceCreate":
        self.anchor_type = str(self.anchor_type or "").strip().upper()
        self.anchor_value = str(self.anchor_value or "").strip()
        self.range_batch_id = str(self.range_batch_id or "").strip().upper()
        self.printed_by = str(self.printed_by or "").strip()
        if self.reprint_reason is not None:
            self.reprint_reason = str(self.reprint_reason).strip()
        return self


class ManualExecutionEntryCreate(BaseModel):
    anchor_type: str = Field(min_length=1)
    anchor_value: str = Field(min_length=1)
    process_context: ProcessContext
    qty: float = Field(gt=0)
    reason_code: ManualFallbackReasonCode
    entered_by: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    witness: str = Field(min_length=1)
    override_at: datetime
    remark: str | None = None
    status: str = "MANUAL_FALLBACK"

    @model_validator(mode="after")
    def normalize_fields(self) -> "ManualExecutionEntryCreate":
        self.anchor_type = str(self.anchor_type or "").strip().upper()
        self.anchor_value = str(self.anchor_value or "").strip()
        self.entered_by = str(self.entered_by or "").strip()
        self.approved_by = str(self.approved_by or "").strip()
        self.witness = str(self.witness or "").strip()
        self.status = str(self.status or "").strip().upper()
        if self.remark is not None:
            self.remark = str(self.remark).strip()
        return self


class ManualExecutionCorrectionCreate(ManualExecutionEntryCreate):
    original_manual_entry_id: int = Field(gt=0)
    status: str = "CORRECTION"


class ManualExecutionEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    anchor_type: str
    anchor_value: str
    process_context: str
    qty: float
    reason_code: str
    entered_by: str
    approved_by: str
    witness: str
    override_at: datetime
    remark: str | None
    status: str
    original_manual_entry_id: int | None
    created_at: datetime


class FallbackSessionCreate(BaseModel):
    line_or_station: str = Field(min_length=1)
    effective_from: datetime
    effective_to: datetime
    reason_code: ManualFallbackReasonCode
    ordered_by: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)
    witness: str = Field(min_length=1)
    status: str = "OPEN"

    @model_validator(mode="after")
    def normalize_fields(self) -> "FallbackSessionCreate":
        self.line_or_station = str(self.line_or_station or "").strip().upper()
        self.ordered_by = str(self.ordered_by or "").strip()
        self.approved_by = str(self.approved_by or "").strip()
        self.witness = str(self.witness or "").strip()
        self.status = str(self.status or "").strip().upper()
        if self.effective_to <= self.effective_from:
            raise ValueError("effective_to must be later than effective_from")
        return self


class DamagedLabelRecordCreate(BaseModel):
    anchor_type: str = Field(min_length=1)
    anchor_value: str = Field(min_length=1)
    related_work_order: int
    label_serial: str = Field(min_length=1)
    damage_stage: str = Field(min_length=1)
    reported_by: str = Field(min_length=1)
    reported_at: datetime
    reason: str = Field(min_length=1)
    replacement_required: bool = False

    @model_validator(mode="after")
    def normalize_fields(self) -> "DamagedLabelRecordCreate":
        self.anchor_type = str(self.anchor_type or "").strip().upper()
        self.anchor_value = str(self.anchor_value or "").strip()
        self.label_serial = str(self.label_serial or "").strip()
        self.damage_stage = str(self.damage_stage or "").strip().upper()
        self.reported_by = str(self.reported_by or "").strip()
        self.reason = str(self.reason or "").strip()
        return self


class FailureQrSheetRecordCreate(BaseModel):
    failure_qr_sheet_no: str = Field(min_length=1)
    attached_by: str = Field(min_length=1)
    attached_at: datetime

    @model_validator(mode="after")
    def normalize_fields(self) -> "FailureQrSheetRecordCreate":
        self.failure_qr_sheet_no = str(self.failure_qr_sheet_no or "").strip().upper()
        self.attached_by = str(self.attached_by or "").strip()
        return self


class DamagedLabelEvidenceChain(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    damaged_label_id: int
    failure_qr_sheet_no: str
    replacement_label_id: int
