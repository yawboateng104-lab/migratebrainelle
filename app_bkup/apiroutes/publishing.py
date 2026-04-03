from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.pg_tables import ContentIdea, GeneratedAsset, PublishedPost, Script, Approval
from app.schemas import PublishedPostResponse
from app.services.publisher import publish_to_instagram, PublisherError

router = APIRouter(prefix="/publish", tags=["publishing"])


@router.post("/content-ideas/{content_idea_id}/instagram", response_model=PublishedPostResponse)
def publish_instagram(content_idea_id: int, db: Session = Depends(get_db)):
    content_idea = db.get(ContentIdea, content_idea_id)
    if not content_idea:
        raise HTTPException(status_code=404, detail="Content idea not found")

    approval = (
        db.query(Approval)
        .filter(Approval.content_idea_id == content_idea_id)
        .first()
    )
    if not approval or approval.status != "approved":
        raise HTTPException(
            status_code=400,
            detail="Content idea must be approved before publishing",
        )

    asset = (
        db.query(GeneratedAsset)
        .filter(GeneratedAsset.content_idea_id == content_idea_id)
        .first()
    )
    if not asset:
        raise HTTPException(status_code=400, detail="Generated asset not found")

    script = (
        db.query(Script)
        .filter(Script.content_idea_id == content_idea_id)
        .first()
    )
    if not script:
        raise HTTPException(status_code=400, detail="Script not found")

    existing = (
        db.query(PublishedPost)
        .filter(PublishedPost.content_idea_id == content_idea_id)
        .first()
    )
    if existing:
        return existing

    print("[PUBLISH DEBUG] asset_url =", asset.asset_url)
    print("[PUBLISH DEBUG] asset_type =", asset.asset_type)

    try:
        published = publish_to_instagram(
            asset_url=asset.asset_url,
            caption=script.caption,
            media_type=asset.asset_type,
        )
    except PublisherError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    post = PublishedPost(
        content_idea_id=content_idea_id,
        platform=published["platform"],
        platform_post_id=published["platform_post_id"],
        publish_status=published["publish_status"],
        caption_used=published["caption_used"],
    )

    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@router.get("/content-ideas/{content_idea_id}", response_model=PublishedPostResponse)
def get_published_post(content_idea_id: int, db: Session = Depends(get_db)):
    post = (
        db.query(PublishedPost)
        .filter(PublishedPost.content_idea_id == content_idea_id)
        .first()
    )
    if not post:
        raise HTTPException(status_code=404, detail="Published post not found")
    return post
