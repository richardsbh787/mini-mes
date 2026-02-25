from fastapi import APIRouter, HTTPException
from app.services.model_routing_service import ModelRoutingService

router = APIRouter(prefix="/v2/e2e", tags=["v2-e2e"])
svc = ModelRoutingService()

@router.get("/bootstrap/{org_id}/{model_code}")
def e2e_bootstrap(org_id: str, model_code: str):
    try:
        row = svc.get_active(org_id=org_id, model_code=model_code)
        steps = row.get("steps") or []
        next_stage = steps[0].get("stage") if steps else None
        return {
            "ok": True,
            "model_code": model_code,
            "next_stage": next_stage,
            "steps": steps,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))