from typing import Any, Dict, Optional
from app.infra.supabase_client import get_supabase

TABLE = "model_routing"

class ModelRoutingRepo:
    def __init__(self):
        self.sb = get_supabase()

    def get_active(self, org_id: str, model_code: str) -> Optional[Dict[str, Any]]:
        resp = (
            self.sb.table(TABLE)
            .select("*")
            .eq("org_id", org_id)
            .eq("model_code", model_code)
            .eq("is_active", True)
            .order("version", desc=True)
            .limit(1)
            .execute()
        )
        data = getattr(resp, "data", None) or []
        return data[0] if data else None

    def deactivate_active(self, org_id: str, model_code: str) -> int:
        resp = (
            self.sb.table(TABLE)
            .update({"is_active": False})
            .eq("org_id", org_id)
            .eq("model_code", model_code)
            .eq("is_active", True)
            .execute()
        )
        data = getattr(resp, "data", None) or []
        return len(data)

    def insert(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = self.sb.table(TABLE).insert(payload).execute()
        data = getattr(resp, "data", None) or []
        if not data:
            raise RuntimeError("Insert model_routing failed: empty response")
        return data[0]