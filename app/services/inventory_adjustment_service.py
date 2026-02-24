from __future__ import annotations
from typing import Any, Dict, List
from datetime import datetime, timezone

from app.repositories.inventory_adjustment_repo import insert_adjustment, insert_adjustment_lines
from app.repositories.stock_ledger_repo import insert_adjustment_ledger, update_ref_id

def commit_adjustment(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Minimal payload:
      org_id (uuid), adj_type ("701" or "702"), reason (text), lines: [{item_id(uuid), qty(float), uom(text), note(optional)}]
    """
    org_id = payload["org_id"]
    adj_type = payload["adj_type"]
    reason = payload.get("reason")

    lines: List[Dict[str, Any]] = payload["lines"]

    hdr = insert_adjustment({
             "org_id": org_id,
             "adjustment_type": adj_type,
             "status": "DRAFT",
             "reason_code": reason,
             "ref_doc": "manual",
       })

    line_rows = []
    ledger_ids = []

    for ln in lines:
        item_id = ln["item_id"]
        qty = float(ln["qty"])
        uom = ln["uom"]
        note = ln.get("note")

        led = insert_adjustment_ledger(org_id=org_id, item_id=item_id, qty=qty, uom=uom, note=note)
        ledger_ids.append(led["id"])

        line_rows.append({
            "org_id": org_id,
            "adjustment_id": hdr["id"],
            "item_id": item_id,
            "qty": qty,
            "note": note,
         
        })

    inserted_lines = insert_adjustment_lines(line_rows)


    return {
        "ok": True,
        "adjustment_id": hdr["id"],
        "lines": inserted_lines,
        "stock_ledger_ids": ledger_ids,
    }