from fastapi import APIRouter, HTTPException
from app.schemas.model_routing import ModelRoutingUpsertIn, ModelRoutingOut
from app.services.model_routing_service import ModelRoutingService

router = APIRouter(prefix="/v2/model-routing", tags=["v2-model-routing"])
svc = ModelRoutingService()

@router.post("/upsert", response_model=ModelRoutingOut)
def upsert_model_routing(payload: ModelRoutingUpsertIn):
    try:
        row = svc.upsert_active(
            org_id=payload.org_id,
            model_code=payload.model_code,
            steps=[s.model_dump() for s in payload.steps],
            version=payload.version,
        )
        return row
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/{org_id}/{model_code}", response_model=ModelRoutingOut)
def get_active_model_routing(org_id: str, model_code: str):
    try:
        row = svc.get_active(org_id=org_id, model_code=model_code)
        return row
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))