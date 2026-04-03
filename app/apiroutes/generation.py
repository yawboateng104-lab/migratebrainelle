from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.pg_tables import Campaign, ContentIdea, Script, VideoPrompt
from app.schemas import ScriptResponse, VideoPromptResponse
from app.services.content_generator import (
    generate_script_from_idea,
    generate_video_prompt_from_script,
)

router = APIRouter(prefix="/generate", tags=["generation"])


def _get_content_idea_or_404(db: Session, content_idea_id: int) -> ContentIdea:
    content_idea = db.get(ContentIdea, content_idea_id)
    if not content_idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Content idea not found",
        )
    return content_idea


def _get_campaign_or_404(db: Session, campaign_id: int) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found",
        )
    return campaign


def _get_script_by_content_idea_id(db: Session, content_idea_id: int) -> Script | None:
    return (
        db.query(Script)
        .filter(Script.content_idea_id == content_idea_id)
        .first()
    )


def _get_video_prompt_by_content_idea_id(db: Session, content_idea_id: int) -> VideoPrompt | None:
    return (
        db.query(VideoPrompt)
        .filter(VideoPrompt.content_idea_id == content_idea_id)
        .first()
    )


@router.post(
    "/content-ideas/{content_idea_id}/script",
    response_model=ScriptResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_script(content_idea_id: int, db: Session = Depends(get_db)):
    content_idea = _get_content_idea_or_404(db, content_idea_id)
    campaign = _get_campaign_or_404(db, content_idea.campaign_id)

    existing_script = _get_script_by_content_idea_id(db, content_idea_id)
    if existing_script:
        return existing_script

    try:
        generated = generate_script_from_idea(
            content_idea=content_idea,
            campaign=campaign,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Script generation failed: {exc}",
        ) from exc

    script = Script(
        content_idea_id=content_idea_id,
        hook=generated["hook"],
        script_text=generated["script_text"],
        caption=generated["caption"],
        hashtags=generated["hashtags"],
        voiceover_text=generated["voiceover_text"],
    )

    db.add(script)
    db.commit()
    db.refresh(script)

    return script


@router.post(
    "/content-ideas/{content_idea_id}/video-prompt",
    response_model=VideoPromptResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_video_prompt(content_idea_id: int, db: Session = Depends(get_db)):
    content_idea = _get_content_idea_or_404(db, content_idea_id)
    campaign = _get_campaign_or_404(db, content_idea.campaign_id)

    script = _get_script_by_content_idea_id(db, content_idea_id)
    if not script:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Generate script first",
        )

    existing_video_prompt = _get_video_prompt_by_content_idea_id(db, content_idea_id)
    if existing_video_prompt:
        return existing_video_prompt

    try:
        generated = generate_video_prompt_from_script(
            content_idea=content_idea,
            campaign=campaign,
            script=script,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video prompt generation failed: {exc}",
        ) from exc

    video_prompt = VideoPrompt(
        content_idea_id=content_idea_id,
        prompt_text=generated["prompt_text"],
        shot_list=generated["shot_list"],
        visual_style=generated["visual_style"],
        camera_notes=generated["camera_notes"],
    )

    db.add(video_prompt)
    db.commit()
    db.refresh(video_prompt)

    return video_prompt
