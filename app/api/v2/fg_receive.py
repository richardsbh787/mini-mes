from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from app.repositories.stock_ledger_repo import insert_ledger
from app.constants.txn_type import RECEIPT
from app.constants.locations import FG_STORE, PACK_PARK




router = APIRouter(prefix="/v2/fg", tags=["v2-fg"])

@router.post("/receive")
def fg_receive(org_id: str, item_id: str, qty: float, uom: str = "ea", ref_type: str = "FG_RECEIVE", ref_id: str | None = None,location_code: str = FG_STORE):
    try:
        row = insert_ledger({
            "org_id": org_id,
            "item_id": item_id,
            "location_code": location_code,
            "txn_type": RECEIPT,
            "qty": abs(qty),
            "uom": uom,
            "ref_type": ref_type,
            "ref_id": ref_id,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"ok": True, "stock_ledger_id": row["id"], "location_code": location_code, "txn_type": RECEIPT}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))