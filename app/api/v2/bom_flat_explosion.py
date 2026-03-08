from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from app.schemas.bom_explosion import FlatExplosionLine, FlatExplosionRequest
from app.services.bom_flat_explosion_service import BOMFlatExplosionService


router = APIRouter(prefix="/v2/bom-explosion", tags=["v2-bom-explosion"])
svc = BOMFlatExplosionService()


@router.post("/flat", response_model=list[FlatExplosionLine])
def explode_flat(payload: FlatExplosionRequest, db: Session = Depends(get_db)):
    return svc.explode_flat(
        db=db,
        parent_system_item_code=payload.parent_system_item_code,
        required_qty=payload.required_qty,
        version_id=payload.version_id,
    )
