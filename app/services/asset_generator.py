import mimetypes
import os
import tempfile
import uuid
from urllib.parse import urlparse

import boto3
import requests

from app.config import settings
from app.integrations.higgsfield import (
    HiggsfieldError,
    generate_image_to_video,
    generate_image_with_reference,
    generate_text_to_image,
    wait_for_image_completion,
    wait_for_video_completion,
)
from app.pg_tables import GeneratedAsset
from app.services.asset_storage import download_video_and_store
from app.services.image_presign_service import get_source_image_url_from_s3_key
from app.services.logo_overlay_service import apply_logo_overlay_to_local_image


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _guess_file_extension_from_response(content_type: str, fallback: str = ".png") -> str:
    guessed_ext = mimetypes.guess_extension((content_type or "").split(";")[0].strip()) or fallback
    if not guessed_ext.startswith("."):
        guessed_ext = f".{guessed_ext}"
    return guessed_ext


def _guess_file_extension_from_url(url: str, fallback: str = ".png") -> str:
    path = urlparse(url).path or ""
    ext = os.path.splitext(path)[1]
    return ext if ext else fallback


def _download_file_to_local(file_url: str, default_ext: str) -> tuple[str, str]:
    response = requests.get(file_url, timeout=300)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type") or ""
    file_ext = _guess_file_extension_from_response(content_type, fallback=default_ext)

    temp_dir = tempfile.gettempdir()
    local_filename = f"generated-asset-{uuid.uuid4()}{file_ext}"
    local_path = os.path.join(temp_dir, local_filename)

    with open(local_path, "wb") as file:
        file.write(response.content)

    return local_path, content_type or mimetypes.guess_type(local_path)[0] or "application/octet-stream"


def _upload_local_file_to_s3(content_idea_id: int, local_path: str, content_type: str, prefix: str) -> dict:
    file_ext = os.path.splitext(local_path)[1] or _guess_file_extension_from_response(content_type, fallback=".bin")

    s3_prefix = (prefix or "").strip()
    if not s3_prefix.endswith("/"):
        s3_prefix = f"{s3_prefix}/"

    s3_key = f"{s3_prefix}content-idea-{content_idea_id}/{uuid.uuid4()}{file_ext}"

    s3_client = boto3.client("s3", region_name=settings.AWS_REGION)
    extra_args = {"ContentType": content_type}
    s3_client.upload_file(local_path, settings.S3_BUCKET_NAME, s3_key, ExtraArgs=extra_args)

    final_url = f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{s3_key}"

    return {
        "key": s3_key,
        "url": final_url,
        "content_type": content_type,
    }


def _cleanup_local_file(local_path: str | None) -> None:
    if not local_path:
        return

    try:
        os.remove(local_path)
    except OSError:
        pass


def _prepare_logo_branded_source_image_if_needed(
    content_idea_id: int,
    source_image_s3_key: str,
    logo_s3_key: str,
) -> str:
    source_image_url = get_source_image_url_from_s3_key(
        source_image_s3_key=source_image_s3_key,
        expires_in=3600,
    )

    local_source_path = None
    try:
        local_source_path, content_type = _download_file_to_local(source_image_url, default_ext=".png")
        apply_logo_overlay_to_local_image(
            local_image_path=local_source_path,
            logo_s3_key=logo_s3_key,
        )

        uploaded = _upload_local_file_to_s3(
            content_idea_id=content_idea_id,
            local_path=local_source_path,
            content_type=content_type or "image/png",
            prefix=settings.S3_IMAGE_PREFIX,
        )

        return get_source_image_url_from_s3_key(
            source_image_s3_key=uploaded["key"],
            expires_in=3600,
        )
    finally:
        _cleanup_local_file(local_source_path)


def generate_asset_from_video_prompt(payload, db) -> GeneratedAsset:
    """
    Unified Higgsfield asset generation flow.

    Supports:
    1. image_to_video
    2. text_to_image
       - plain text prompt
       - text prompt with reference image (using source_image_s3_key)
    3. optional logo overlay for generated image outputs
       and for source-image video generation by branding the source image first
    """
    content_idea_id = payload.content_idea_id
    prompt_text = _normalize_text(getattr(payload, "prompt_text", None))
    generation_mode = _normalize_text(getattr(payload, "generation_mode", None)) or "image_to_video"
    source_image_s3_key = _normalize_text(getattr(payload, "source_image_s3_key", None))
    logo_s3_key = _normalize_text(getattr(payload, "logo_s3_key", None))

    if not prompt_text:
        raise HiggsfieldError("prompt_text is required")

    existing = (
        db.query(GeneratedAsset)
        .filter(GeneratedAsset.content_idea_id == content_idea_id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()

    if generation_mode == "text_to_image":
        if source_image_s3_key:
            source_image_url = get_source_image_url_from_s3_key(
                source_image_s3_key=source_image_s3_key,
                expires_in=3600,
            )
            initial_result = generate_image_with_reference(
                image_url=source_image_url,
                prompt_text=prompt_text,
            )
        else:
            initial_result = generate_text_to_image(prompt_text=prompt_text)

        status_url = initial_result.get("status_url")
        if not status_url:
            raise HiggsfieldError(f"No status_url returned from Higgsfield: {initial_result}")

        final_result = wait_for_image_completion(
            status_url=status_url,
            max_attempts=30,
            sleep_seconds=10,
        )

        images = final_result.get("images") or []
        if not images:
            raise HiggsfieldError(f"No images returned from Higgsfield: {final_result}")

        image_url = images[0].get("url") if isinstance(images[0], dict) else None
        if not image_url:
            raise HiggsfieldError(f"No image URL returned from Higgsfield: {final_result}")

        local_image_path = None
        try:
            local_image_path, content_type = _download_file_to_local(
                image_url,
                default_ext=_guess_file_extension_from_url(image_url, fallback=".png"),
            )

            if logo_s3_key:
                apply_logo_overlay_to_local_image(
                    local_image_path=local_image_path,
                    logo_s3_key=logo_s3_key,
                )

            stored_image = _upload_local_file_to_s3(
                content_idea_id=content_idea_id,
                local_path=local_image_path,
                content_type=content_type or "image/png",
                prefix=settings.S3_IMAGE_PREFIX,
            )

            asset = GeneratedAsset(
                content_idea_id=content_idea_id,
                provider="higgsfield",
                asset_url=stored_image["url"],
                thumbnail_url=None,
                asset_type="image",
                status="generated",
            )

            db.add(asset)
            db.commit()
            db.refresh(asset)
            return asset
        finally:
            _cleanup_local_file(local_image_path)

    if generation_mode != "image_to_video":
        raise HiggsfieldError(f"Unsupported Higgsfield generation mode: {generation_mode}")

    if not source_image_s3_key:
        raise HiggsfieldError("source_image_s3_key is required for image_to_video")

    if logo_s3_key:
        source_image_url = _prepare_logo_branded_source_image_if_needed(
            content_idea_id=content_idea_id,
            source_image_s3_key=source_image_s3_key,
            logo_s3_key=logo_s3_key,
        )
    else:
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

    asset = GeneratedAsset(
        content_idea_id=content_idea_id,
        provider="higgsfield",
        asset_url=stored_video["url"],
        thumbnail_url=None,
        asset_type="video",
        status="generated",
    )

    db.add(asset)
    db.commit()
    db.refresh(asset)

    return asset
