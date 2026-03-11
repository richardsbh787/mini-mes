from datetime import datetime

from pydantic import BaseModel


class WorkOrderMaterialIssueCorrectionQueryResponse(BaseModel):
    correction_event_id: int
    original_issue_event_id: int
    snapshot_id: int
    work_order_no: str
    reason_code: str
    reason_note: str | None
    corrected_by: str
    corrected_at: datetime
