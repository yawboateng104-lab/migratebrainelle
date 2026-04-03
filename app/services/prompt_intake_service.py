from sqlalchemy.orm import Session

from app.services.creative_request_service import create_creative_request
from app.services.prompt_resolution_service import resolve_creative_request


def intake_and_resolve_creative_request(db: Session, payload):
    creative_request = create_creative_request(db, payload)
    resolved_spec = resolve_creative_request(db, creative_request.id)
    return {
        "creative_request": creative_request,
        "resolved_spec": resolved_spec,
    }
