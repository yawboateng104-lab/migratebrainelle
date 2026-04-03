from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import CreativeFeedbackSignalCreate
from app.services.analytics_signal_service import create_feedback_signal, get_active_feedback_signals

router = APIRouter(prefix="/analytics-feedback", tags=["analytics-feedback"])


@router.post("")
def create_feedback_signal_route(payload: CreativeFeedbackSignalCreate, db: Session = Depends(get_db)):
    return create_feedback_signal(db, payload)


@router.get("/clients/{client_id}")
def get_feedback_signals_route(client_id: int, db: Session = Depends(get_db)):
    return get_active_feedback_signals(db, client_id)
