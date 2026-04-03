from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import MarketingSummaryResponse
from app.services.insights_service import build_marketing_summary

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/marketing-summary", response_model=MarketingSummaryResponse)
def get_marketing_summary(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    return build_marketing_summary(db=db, days=days)
