from app.integrations.higgsfield import (
    HiggsfieldError,
    generate_image_to_video,
    wait_for_video_completion,
)
from app.pg_tables import GeneratedAsset
from app.services.asset_storage import download_video_and_store
from app.services.image_presign_service import get_source_image_url_from_s3_key


def generate_asset_from_video_prompt(payload, db) -> GeneratedAsset:
    """
    End-to-end flow:
    1. Presign source image from S3 key
    2. Send image + prompt to Higgsfield
    3. Poll until completed
    4. Download finished MP4
    5. Upload MP4 to S3
    6. Save GeneratedAsset row using FINAL S3 URL
    """
    content_idea_id = payload.content_idea_id
    prompt_text = payload.prompt_text.strip()
    source_image_s3_key = payload.source_image_s3_key.strip()

    if not source_image_s3_key:
        raise HiggsfieldError("source_image_s3_key is required")

    if not prompt_text:
        raise HiggsfieldError("prompt_text is required")

    source_image_url = get_source_image_url_from_s3_key(
        source_image_s3_key=source_image_s3_key,
        expires_in=3600,
    )

    initial_result = generate_image_to_video(
        image_url=source_image_url,
        prompt_text=prompt_text,
    )

    status_url = initial_result.get("status_url")
    if not status_url:
        raise HiggsfieldError(f"No status_url returned from Higgsfield: {initial_result}")

    final_result = wait_for_video_completion(
        status_url=status_url,
        max_attempts=30,
        sleep_seconds=10,
    )

    source_video_url = final_result.get("video", {}).get("url")
    if not source_video_url:
        raise HiggsfieldError(f"No video URL returned from Higgsfield: {final_result}")

    stored_video = download_video_and_store(
        content_idea_id=content_idea_id,
        source_video_url=source_video_url,
    )

    existing = (
        db.query(GeneratedAsset)
        .filter(GeneratedAsset.content_idea_id == content_idea_id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
    
#######################vid provider change i made for testing
    video_provider = "higgsfield"   # or "runway", "luma", etc.
    asset = GeneratedAsset(
    content_idea_id=content_idea_id,
    provider=video_provider,
    asset_url=stored_video["url"],  # final public S3 URL
    thumbnail_url=None,
    asset_type="video",
    status="generated",        
    )

    db.add(asset)
    db.commit()
    db.refresh(asset)

    return asset
