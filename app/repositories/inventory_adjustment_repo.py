from __future__ import annotations
from typing import Any, Dict, List
from app.infra.supabase_client import sb_table

HDR = "inventory_adjustment"
LIN = "inventory_adjustment_line"

def insert_adjustment(header: Dict[str, Any]) -> Dict[str, Any]:
    resp = sb_table(HDR).insert(header).execute()
    data = getattr(resp, "data", None)
    if not data:
        raise RuntimeError("Supabase insert inventory_adjustment returned empty data")
    return data[0]

def insert_adjustment_lines(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    resp = sb_table(LIN).insert(lines).execute()
    data = getattr(resp, "data", None)
    return data or []


def insert_adjustment_line(line: Dict[str, Any]) -> Dict[str, Any]:
    resp = sb_table(LIN).insert(line).execute()
    data = getattr(resp, "data", None)
    if not data:
        raise RuntimeError("Supabase insert inventory_adjustment_line returned empty data")
    return data[0]