from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, List


@dataclass(frozen=True)
class ConsumptionRequest:
    org_id: str
    work_order_id: str
    bom_id: Optional[str]
    item_id: str
    location_id: Optional[str]
    qty: Decimal
    direction: str  # "CONSUME" or "REVERSE"
    reason: Optional[str] = None


@dataclass(frozen=True)
class LedgerEntry:
    org_id: str
    item_id: str
    location_id: Optional[str]
    txn_type: str  # "ISSUE" or "RECEIPT" etc.
    qty: Decimal
    uom: str = "PCS"
    ref_type: str
    ref_id: str
    note: Optional[str] = None


def build_ledger_entry(req: ConsumptionRequest) -> LedgerEntry:
    """
    Rule:
    - CONSUME -> ISSUE (qty negative not used; we keep qty positive and encode meaning in txn_type)
    - REVERSE -> RECEIPT
    """
    if req.direction not in ("CONSUME", "REVERSE"):
        raise ValueError("direction must be CONSUME or REVERSE")

    txn_type = "ISSUE" if req.direction == "CONSUME" else "RECEIPT"

    return LedgerEntry(
        org_id=req.org_id,
        item_id=req.item_id,
        location_id=req.location_id,
        txn_type=txn_type,
        qty=req.qty,
        ref_type="work_order",
        ref_id=req.work_order_id,
        note=req.reason,
    )


