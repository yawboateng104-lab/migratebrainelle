# app/routes/pipeline.py
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.cinematic_pipeline_service import run_cinematic_pipeline
from app.integrations.s3 import generate_presigned_get_url 
from app.config import settings
from app.pg_tables import ContentIdea, Script, VideoPrompt  # adapt to your models


router = APIRouter(prefix="/cinematic_pipeline", tags=["cinematic_pipeline"])


class CinematicRunRequest(BaseModel):
    source_image_s3_key: str
    voice_id: str | None = None


@router.post("/content-ideas/{content_idea_id}/run-cinematic")
def run_cinematic(
    content_idea_id: int,
    payload: CinematicRunRequest,
    db: Session = Depends(get_db),
):
    content_idea = db.query(ContentIdea).filter(ContentIdea.id == content_idea_id).first()
    if not content_idea:
        raise HTTPException(status_code=404, detail="Content idea not found")

    script_row = (
        db.query(Script)
        .filter(Script.content_idea_id == content_idea_id)
        .order_by(Script.id.desc())
        .first()
    )
    if not script_row:
        raise HTTPException(status_code=400, detail="No script found for content idea")

    video_prompt_row = (
        db.query(VideoPrompt)
        .filter(VideoPrompt.content_idea_id == content_idea_id)
        .order_by(VideoPrompt.id.desc())
        .first()
    )
    if not video_prompt_row:
        raise HTTPException(status_code=400, detail="No video prompt found for content idea")

    source_image_url = generate_presigned_get_url(
    bucket=settings.S3_BUCKET_NAME,
    key=payload.source_image_s3_key,
    expires_in=3600,
)

    
    # For V1, split the prompt into two simple shots.
    # Later you can store these separately in DB.
    shot_1_prompt = (
        "Vertical cinematic brand reel. Confident business owner in a modern office, "
        "subtle camera push-in, natural movement, warm daylight, premium commercial aesthetic."
    )
    shot_2_prompt = (
        "Vertical premium social ad shot. Same subject consistency, slightly wider framing, "
        "clean modern background, elegant motion, strong conversion-focused brand feel."
    )

    try:
        result = run_cinematic_pipeline(
            db=db,
            content_idea_id=content_idea_id,
            source_image_url=source_image_url,
            script_text=script_row.script_text,
            caption_text="",
            shot_1_prompt=shot_1_prompt,
            shot_2_prompt=shot_2_prompt,
            voice_id=payload.voice_id,
        )
        return {
            "status": "generated",
            **result,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
