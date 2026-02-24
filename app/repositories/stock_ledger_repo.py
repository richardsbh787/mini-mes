from __future__ import annotations
from typing import Any, Dict, List
from app.infra.supabase_client import sb_table
from datetime import datetime, timezone

TABLE = "stock_ledger"

def insert_ledger(entry: Dict[str, Any]) -> Dict[str, Any]:
    resp = sb_table(TABLE).insert(entry).execute()
    data = getattr(resp, "data", None)
    if not data:
        raise RuntimeError("Supabase insert stock_ledger returned empty data")
    return data[0]

def list_ledger(org_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    resp = (
        sb_table(TABLE)
        .select("*")
        .eq("org_id", org_id)
        .order("occurred_at", desc=True)
        .limit(limit)
        .execute()
    )
    data = getattr(resp, "data", None)
    return data or []

def update_ref_id(ledger_id: str, ref_id: str) -> None:
    sb_table(TABLE).update({"ref_id": ref_id}).eq("id", ledger_id).execute()


from typing import Optional

def get_onhand(org_id: str, item_id: str, location_id: Optional[str] = None) -> float:
    q = sb_table(TABLE).select("qty").eq("org_id", org_id).eq("item_id", item_id)
    if location_id is not None:
        q = q.eq("location_id", location_id)
    resp = q.execute()
    data = getattr(resp, "data", None) or []
    return float(sum(float(r["qty"]) for r in data))


def insert_adjustment_ledger(org_id: str, item_id: str, qty: float, uom: str, note: str | None = None) -> Dict[str, Any]:
    return insert_ledger({
        "org_id": org_id,
        "item_id": item_id,
        "txn_type": "ADJUSTMENT",
        "qty": qty,
        "uom": uom,
        "ref_type": "INVENTORY_ADJUSTMENT",
        "note": note,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    })