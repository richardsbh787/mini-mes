from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from app.schemas.work_order_bom_preview import (
    WorkOrderBOMPreviewRequest,
    WorkOrderBOMPreviewResponse,
)
from app.services.bom_flat_explosion_service import BOMFlatExplosionService
from app.services.bom_tree_explosion_service import BOMTreeExplosionService


router = APIRouter(prefix="/v2/work-order", tags=["v2-work-order-bom-preview"])
flat_svc = BOMFlatExplosionService()
tree_svc = BOMTreeExplosionService()


@router.post("/bom-preview", response_model=WorkOrderBOMPreviewResponse)
def work_order_bom_preview(payload: WorkOrderBOMPreviewRequest, db: Session = Depends(get_db)):
    tree_result = tree_svc.explode_tree(
        db=db,
        parent_system_item_code=payload.parent_system_item_code,
        required_qty=payload.work_order_qty,
        version_id=payload.version_id,
    )
    selected_version_id = tree_result["version_id"]

    flat_materials = flat_svc.explode_flat(
        db=db,
        parent_system_item_code=payload.parent_system_item_code,
        required_qty=payload.work_order_qty,
        version_id=selected_version_id,
    )

    return {
        "parent_system_item_code": payload.parent_system_item_code,
        "work_order_qty": payload.work_order_qty,
        "version_id": selected_version_id,
        "flat_materials": flat_materials,
        "tree": tree_result["tree"],
    }
