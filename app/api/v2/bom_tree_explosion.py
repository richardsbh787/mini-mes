from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from app.schemas.bom_tree_explosion import TreeExplosionRequest, TreeExplosionResponse
from app.services.bom_tree_explosion_service import BOMTreeExplosionService


router = APIRouter(prefix="/v2/bom/explode", tags=["v2-bom-tree-explosion"])
svc = BOMTreeExplosionService()


@router.post("/tree", response_model=TreeExplosionResponse)
def explode_tree(payload: TreeExplosionRequest, db: Session = Depends(get_db)):
    return svc.explode_tree(
        db=db,
        parent_system_item_code=payload.parent_system_item_code,
        required_qty=payload.required_qty,
        version_id=payload.version_id,
    )
