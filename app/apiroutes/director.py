from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import DirectorBriefCreate
from app.services.director_brief_service import build_creative_request_from_director_brief
from app.services.prompt_intake_service import intake_and_resolve_creative_request

router = APIRouter(prefix="/director", tags=["director"])


@router.post("/brief")
def create_from_director_brief(payload: DirectorBriefCreate, db: Session = Depends(get_db)):
    creative_request_payload = build_creative_request_from_director_brief(payload)
    result = intake_and_resolve_creative_request(db, creative_request_payload)

    return {
        "creative_request_id": result["creative_request"].id,
        "creative_request_status": result["creative_request"].status,
        "resolved_spec_id": result["resolved_spec"].id,
        "workflow": result["resolved_spec"].workflow,
        "provider": result["resolved_spec"].provider,
    }
