from __future__ import annotations
from typing import Any, Dict
from datetime import datetime, timezone
from app.repositories.stock_ledger_repo import update_ref_id

from app.repositories.stock_ledger_repo import insert_ledger
from app.repositories.consumption_event_repo import insert_event

def commit_consume(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    payload should already be validated by FastAPI schema layer.
    Minimal required keys:
      org_id, item_id, qty, uom
    Optional:
      warehouse_id, location_id
    """
    org_id = payload["org_id"]
    item_id = payload["item_id"]
    qty = payload["qty"]
    uom = payload["uom"]

    warehouse_id = payload.get("warehouse_id")
    location_id = payload.get("location_id")

    # ISSUE: store as negative qty (locked convention)
    ledger_row = insert_ledger({
        "org_id": org_id,
        "item_id": item_id,
        "txn_type": "ISSUE",
        "qty": -abs(qty),
        "uom": uom,
        "ref_type": "CONSUMPTION_EVENT",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    })

    ev_row = insert_event({
        "org_id": org_id,
        "work_order_id": "00000000-0000-0000-0000-000000000000",
        "bom_id": None,
        "item_id": item_id,
        "location_id": None,
        "qty": qty,
        "direction": "CONSUME",
        "reason": "commit",
        "stock_ledger_id": ledger_row["id"],
    })
    update_ref_id(ledger_row["id"], ev_row["id"]) 
    
    return {
        "ok": True,
        "stock_ledger_id": ledger_row["id"],
        "consumption_event_id": ev_row["id"],
        "txn_type": "ISSUE",
        "qty": qty,
    }


def preview_consume(payload: Dict[str, Any]) -> Dict[str, Any]:
    org_id = payload["org_id"]
    item_id = payload["item_id"]
    qty = payload["qty"]
    uom = payload["uom"]

    ledger_entry = {
        "org_id": org_id,
        "item_id": item_id,
        "txn_type": "ISSUE",
        "qty": -abs(qty),
        "uom": uom,
        "ref_type": "CONSUMPTION_EVENT",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }

    event_entry = {
        "org_id": org_id,
        "work_order_id": "00000000-0000-0000-0000-000000000000",
        "bom_id": None,
        "item_id": item_id,
        "location_id": None,
        "qty": qty,
        "direction": "CONSUME",
        "reason": "preview",
    }

    return {"ok": True, "ledger_entry": ledger_entry, "event_entry": event_entry}

