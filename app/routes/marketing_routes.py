"""Rutas administrativas del módulo Marketing / MindHigh."""
from fastapi import APIRouter, Depends

from app.dependencies import require_roles
from app.schemas.marketing import (
    CampaignBriefIn,
    MarketingCampaignOut,
    MarketingStatusOut,
)
from app.services.mh_core_marketing_service import MhCoreMarketingService


router = APIRouter(
    prefix="/marketing",
    tags=["Marketing"],
    dependencies=[Depends(require_roles("admin"))],
)


@router.get("/status", response_model=MarketingStatusOut)
def marketing_status():
    return MhCoreMarketingService().obtener_estado()


@router.post("/campaigns/draft", response_model=MarketingCampaignOut)
def create_campaign_draft(brief: CampaignBriefIn):
    return MhCoreMarketingService().crear_borrador(brief.model_dump(mode="json"))
