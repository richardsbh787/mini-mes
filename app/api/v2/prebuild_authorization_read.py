from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.schemas.step42_prebuild_authorization import (
    PrebuildAuthorizationDetailQuery,
    PrebuildAuthorizationDetailResponse,
    PrebuildAuthorizationListQuery,
    PrebuildAuthorizationListResponse,
    PrebuildAuthorizationStatus,
)
from app.services.step42_prebuild_authorization import (
    get_prebuild_authorization_detail,
    list_prebuild_authorizations,
)
from database import get_db


router = APIRouter(prefix="/v2/prebuild-authorizations", tags=["v2-prebuild-authorization-read"])


@router.get("", response_model=PrebuildAuthorizationListResponse)
def prebuild_authorization_list(
    work_order_id: int | None = None,
    status: PrebuildAuthorizationStatus | None = None,
    requested_by: str | None = None,
    approved_by: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
) -> PrebuildAuthorizationListResponse:
    return list_prebuild_authorizations(
        db,
        query=PrebuildAuthorizationListQuery(
            work_order_id=work_order_id,
            status=status,
            requested_by=requested_by,
            approved_by=approved_by,
            date_from=date_from,
            date_to=date_to,
            page=page,
            page_size=page_size,
        ),
    )


@router.get("/detail", response_model=PrebuildAuthorizationDetailResponse)
def prebuild_authorization_detail(
    prebuild_auth_id: int | None = None,
    prebuild_auth_no: str | None = None,
    db: Session = Depends(get_db),
) -> PrebuildAuthorizationDetailResponse:
    return get_prebuild_authorization_detail(
        db,
        query=PrebuildAuthorizationDetailQuery(
            prebuild_auth_id=prebuild_auth_id,
            prebuild_auth_no=prebuild_auth_no,
        ),
    )
