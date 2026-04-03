from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import VideoEditRequestCreate
from app.services.video_edit_service import create_edit_revision_from_creative_request

router = APIRouter(prefix="/video-edits", tags=["video-edits"])


@router.post("")
def create_video_edit_revision(payload: VideoEditRequestCreate, db: Session = Depends(get_db)):
    try:
        result = create_edit_revision_from_creative_request(db, payload)
        return {
            "original_creative_request_id": payload.creative_request_id,
            "new_creative_request_id": result["creative_request"].id,
            "new_creative_request_status": result["creative_request"].status,
            "resolved_spec_id": result["resolved_spec"].id,
            "workflow": result["resolved_spec"].workflow,
            "provider": result["resolved_spec"].provider,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
