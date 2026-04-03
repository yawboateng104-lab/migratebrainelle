from sqlalchemy.orm import Session

from app.pg_tables import CreativeFeedbackSignal


def create_feedback_signal(db: Session, payload):
    signal = CreativeFeedbackSignal(
        client_id=payload.client_id,
        campaign_id=payload.campaign_id,
        creative_request_id=payload.creative_request_id,
        signal_source=payload.signal_source,
        signal_type=payload.signal_type,
        title=payload.title,
        summary=payload.summary,
        recommendation=payload.recommendation,
        priority_score=payload.priority_score,
        structured_signal_json=payload.structured_signal_json,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


def get_active_feedback_signals(db: Session, client_id: int, limit: int = 20):
    return (
        db.query(CreativeFeedbackSignal)
        .filter(CreativeFeedbackSignal.client_id == client_id)
        .order_by(CreativeFeedbackSignal.created_at.desc())
        .limit(limit)
        .all()
    )
