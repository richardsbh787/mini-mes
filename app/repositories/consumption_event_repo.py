from __future__ import annotations
from typing import Any, Dict
from app.infra.supabase_client import sb_table

TABLE = "consumption_event"

def insert_event(ev: Dict[str, Any]) -> Dict[str, Any]:
    resp = sb_table(TABLE).insert(ev).execute()
    data = getattr(resp, "data", None)
    if not data:
        raise RuntimeError("Supabase insert consumption_event returned empty data")
    return data[0]