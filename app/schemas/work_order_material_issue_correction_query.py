from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkOrderMaterialIssueCorrectionQueryResponse(BaseModel):
    """Read-only correction governance query/display contract.

    This schema belongs only to the correction query surface used for minimal
    governance lookup and display. It is serialized from persisted correction
    events for read-only query responses and must not be treated as a posting
    model, mutation payload, command model, write model, approval action model,
    or general-purpose correction domain entity.
    """

    model_config = ConfigDict(
        title="Correction Governance Query Response",
        json_schema_extra={
            "description": (
                "Read-only correction governance query/display schema used by the "
                "minimal correction lookup and list APIs. Not a posting, mutation, "
                "write, command, or approval-execution model."
            )
        },
    )

    correction_event_id: int = Field(
        ...,
        description="Read-only correction event identifier for governance lookup and display.",
    )
    original_issue_event_id: int = Field(
        ...,
        description="Read-only original issue event identifier used for trace confirmation and lookup.",
    )
    snapshot_id: int = Field(
        ...,
        description="Read-only snapshot identifier exposed only as part of the query/display contract.",
    )
    work_order_no: str = Field(
        ...,
        description="Read-only work order number for display and minimal governance search.",
    )
    reason_code: str = Field(
        ...,
        description="Read-only correction reason code for lookup/display only; not a writable input field.",
    )
    reason_note: str | None = Field(
        None,
        description="Read-only correction reason note for lookup/display only; not a posting or update field.",
    )
    corrected_by: str = Field(
        ...,
        description="Read-only operator/accountability display field; not a command or approval input.",
    )
    corrected_at: datetime = Field(
        ...,
        description="Read-only correction timestamp for governance lookup and display only.",
    )
