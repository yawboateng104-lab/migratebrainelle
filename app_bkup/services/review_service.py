from urllib.parse import urlparse

from app.config import settings
from app.integrations.s3 import generate_presigned_get_url
from app.pg_tables import GeneratedAsset, PublishedPost, Script
from app.services.client_instagram_service import (
    ClientInstagramError,
    get_instagram_credentials_for_content_idea,
)
from app.services.publisher import publish_to_instagram


class ReviewError(Exception):
    pass


def extract_s3_key_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path.lstrip("/")


def build_publishable_asset_url(asset_url: str) -> str:
    if asset_url.startswith("https://") and settings.S3_BUCKET_NAME in asset_url:
        video_key = extract_s3_key_from_url(asset_url)
        return generate_presigned_get_url(
            bucket=settings.S3_BUCKET_NAME,
            key=video_key,
            expires_in=3600,
        )

    if asset_url.startswith("https://"):
        return asset_url

    raise ReviewError("Asset URL must be a public HTTPS URL before publishing")


def approve_and_publish_generated_asset(generated_asset_id: int, db):
    asset = db.get(GeneratedAsset, generated_asset_id)
    if not asset:
        raise ReviewError("Generated asset not found")

    if asset.status == "published":
        raise ReviewError("Generated asset is already published")

    if asset.status == "rejected":
        raise ReviewError("Rejected assets cannot be published")

    script = (
        db.query(Script)
        .filter(Script.content_idea_id == asset.content_idea_id)
        .first()
    )
    if not script:
        raise ReviewError("Script not found for generated asset")

    existing_post = (
        db.query(PublishedPost)
        .filter(PublishedPost.generated_asset_id == asset.id)
        .first()
    )
    if existing_post:
        asset.status = "published"
        db.add(asset)
        db.commit()
        db.refresh(asset)

        return {
            "generated_asset_id": asset.id,
            "content_idea_id": asset.content_idea_id,
            "published_post_id": existing_post.id,
            "publish_status": existing_post.publish_status,
            "asset_url": asset.asset_url,
            "caption_used": existing_post.caption_used,
            "review_status": asset.status,
        }

    try:
        creds = get_instagram_credentials_for_content_idea(
            content_idea_id=asset.content_idea_id,
            db=db,
        )
    except ClientInstagramError as exc:
        raise ReviewError(str(exc)) from exc

    asset.status = "approved"
    db.add(asset)
    db.commit()
    db.refresh(asset)

    publishable_asset_url = build_publishable_asset_url(asset.asset_url)

    published = publish_to_instagram(
        asset_url=publishable_asset_url,
        caption=script.caption,
        media_type=asset.asset_type,
        graph_base_url=creds["graph_base_url"],
        access_token=creds["access_token"],
        instagram_account_id=creds["instagram_account_id"],
    )

    published_post = PublishedPost(
        content_idea_id=asset.content_idea_id,
        generated_asset_id=asset.id,
        workflow=asset.provider if asset.provider else "unknown",
        provider=asset.provider if asset.provider else "unknown",
        platform=published["platform"],
        platform_post_id=published["platform_post_id"],
        publish_status=published["publish_status"],
        caption_used=published["caption_used"],
    )
    db.add(published_post)

    asset.status = "published"
    db.add(asset)

    db.commit()
    db.refresh(asset)
    db.refresh(published_post)

    return {
        "generated_asset_id": asset.id,
        "content_idea_id": asset.content_idea_id,
        "published_post_id": published_post.id,
        "publish_status": published_post.publish_status,
        "asset_url": asset.asset_url,
        "caption_used": script.caption,
        "review_status": asset.status,
    }


def reject_generated_asset(generated_asset_id: int, db):
    asset = db.get(GeneratedAsset, generated_asset_id)
    if not asset:
        raise ReviewError("Generated asset not found")

    if asset.status == "published":
        raise ReviewError("Published assets cannot be rejected")

    asset.status = "rejected"
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return {
        "generated_asset_id": asset.id,
        "content_idea_id": asset.content_idea_id,
        "review_status": asset.status,
    }
