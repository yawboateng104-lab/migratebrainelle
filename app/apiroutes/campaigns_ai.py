from fastapi import APIRouter
from app.schemas import CampaignBootstrapRequest
from app.services.campaign_planner_service import bootstrap_campaign_plan

router = APIRouter(prefix="/campaigns-ai", tags=["campaigns-ai"])


@router.post("/bootstrap")
def bootstrap_campaigns_route(payload: CampaignBootstrapRequest):
    return bootstrap_campaign_plan(payload.dict())
