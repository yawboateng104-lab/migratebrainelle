from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.pg_tables import Campaign, ContentIdea
from app.schemas import ContentIdeaCreate, ContentIdeaResponse

router = APIRouter(prefix="/content-ideas", tags=["content-ideas"])


@router.post("", response_model=ContentIdeaResponse)
def create_content_idea(payload: ContentIdeaCreate, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, payload.campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    content_idea = ContentIdea(**payload.model_dump())
    db.add(content_idea)
    db.commit()
    db.refresh(content_idea)
    return content_idea


@router.get("", response_model=list[ContentIdeaResponse])
def list_content_ideas(db: Session = Depends(get_db)):
    return db.query(ContentIdea).order_by(ContentIdea.id.desc()).all()
