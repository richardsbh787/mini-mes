from __future__ import annotations
from typing import Any, Dict
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException

from app.repositories.stock_ledger_repo import update_ref_id, insert_ledger, get_onhand
from app.repositories.consumption_event_repo import insert_event
from app.constants.txn_type import ISSUE
from app.constants.locations import LINE


def commit_consume(payload: Dict[str, Any]) -> Dict[str, Any]:
    org_id = payload["org_id"]
    item_id = payload["item_id"]
    uom = payload["uom"]
    model_code = payload.get("model_code")

    # 1) qty 强制为正数输入（系统自己写负数到ledger）
    try:
        qty = Decimal(str(payload["qty"]))
    except Exception:
        raise HTTPException(status_code=400, detail="qty must be a number")

    if qty <= 0:
        raise HTTPException(status_code=400, detail="qty must be > 0")

    # 2) 幂等键（防 Swagger 双击/重试）
    #   你先不改表也可以：把它塞进 reason，至少能追溯/人工排查重复
    client_txn_id = payload.get("client_txn_id")
    if not client_txn_id:
        raise HTTPException(status_code=400, detail="client_txn_id is required (uuid)")

    # 3) 防负库存：写入前查 onhand
    onhand = Decimal(str(get_onhand(org_id=org_id, item_id=item_id, location_code=LINE)))
    if onhand < qty:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient stock at {LINE}: onhand={onhand} {uom}, required={qty} {uom}"
        )

    # ISSUE: ledger 存负数（锁定约定）
    ledger_row = insert_ledger({
        "org_id": org_id,
        "item_id": item_id,
        "location_code": LINE,
        "txn_type": ISSUE,
        "qty": float(-qty),  # 或保持 Decimal 看你repo是否支持
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
        "qty": float(qty),  # 事件存正数（更清晰）
        "direction": "CONSUME",
        "reason": f"commit:{client_txn_id}",  # 轻量幂等/追溯
        "stock_ledger_id": ledger_row["id"],
        "model_code": model_code,
    })

    update_ref_id(ledger_row["id"], ev_row["id"])

    return {
        "ok": True,
        "stock_ledger_id": ledger_row["id"],
        "consumption_event_id": ev_row["id"],
        "txn_type": ISSUE,
        "location_code": LINE,
        "qty": float(qty),
        "uom": uom,
        "onhand_before": float(onhand),
        "onhand_after": float(onhand - qty),
    }

def preview_consume(payload: Dict[str, Any]) -> Dict[str, Any]:
    org_id = payload["org_id"]
    item_id = payload["item_id"]
    qty = payload["qty"]
    uom = payload["uom"]

    ledger_entry = {
        "org_id": org_id,
        "item_id": item_id,
        "location_code": LINE,
        "txn_type": ISSUE,
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
        "qty": qty,
        "direction": "CONSUME",
        "reason": "preview",
    }

    return {"ok": True, "ledger_entry": ledger_entry, "event_entry": event_entry}

