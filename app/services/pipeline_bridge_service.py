from sqlalchemy.orm import Session

from app.services.creative_request_service import (
    get_creative_media_inputs,
    get_latest_resolved_spec_for_request,
)


SUPPORTED_PIPELINE_WORKFLOWS = {
    "higgsfield",
    "runway_cinematic",
}


SUPPORTED_GENERATION_MODES = {
    "image_to_video",
    "text_to_image",
}


def _get_primary_source_image(media_inputs):
    primary_source_image = next(
        (
            media
            for media in media_inputs
            if media.media_role == "source_image" and media.is_primary is True
        ),
        None,
    )

    if primary_source_image:
        return primary_source_image

    return next(
        (
            media
            for media in media_inputs
            if media.media_role == "source_image"
        ),
        None,
    )


def _normalize_generation_mode(value) -> str | None:
    if not isinstance(value, str):
        return None

    normalized = value.strip().lower()
    if normalized in SUPPORTED_GENERATION_MODES:
        return normalized

    return None


def _normalize_workflow(resolved) -> str:
    workflow = getattr(resolved, "workflow", None)
    provider = getattr(resolved, "provider", None)
    generation_mode = getattr(resolved, "generation_mode", None)

    if isinstance(workflow, str):
        workflow = workflow.strip()

    if isinstance(provider, str):
        provider = provider.strip().lower()

    if isinstance(generation_mode, str):
        generation_mode = generation_mode.strip().lower()

    if workflow in SUPPORTED_PIPELINE_WORKFLOWS:
        return workflow

    # Protect against bad resolved data where generation_mode was written into workflow
    if workflow == "image_to_video":
        if provider == "higgsfield":
            return "higgsfield"
        if provider == "runway":
            return "runway_cinematic"

    # Fallback by provider if workflow is missing or invalid
    if provider == "higgsfield":
        return "higgsfield"

    if provider == "runway":
        return "runway_cinematic"

    raise ValueError(
        f"Unsupported resolved workflow '{workflow}' for provider '{provider}' "
        f"and generation_mode '{generation_mode}'"
    )


def build_existing_pipeline_payload_from_creative_request(
    db: Session,
    creative_request_id: int,
) -> dict:
    resolved = get_latest_resolved_spec_for_request(db, creative_request_id)
    if not resolved:
        raise ValueError("Resolved creative spec not found")

    media_inputs = get_creative_media_inputs(db, creative_request_id)
    primary_source_image = _get_primary_source_image(media_inputs)

    normalized_workflow = _normalize_workflow(resolved)
    normalized_generation_mode = _normalize_generation_mode(getattr(resolved, "generation_mode", None))

    provider_payload_json = getattr(resolved, "provider_payload_json", None) or {}
    logo_s3_key = provider_payload_json.get("logo_s3_key")

    payload = {
        "workflow": normalized_workflow,
    }

    if normalized_generation_mode:
        payload["generation_mode"] = normalized_generation_mode

    if primary_source_image and primary_source_image.storage_key:
        payload["source_image_s3_key"] = primary_source_image.storage_key

    if isinstance(logo_s3_key, str) and logo_s3_key.strip():
        payload["logo_s3_key"] = logo_s3_key.strip()

    return payload


def build_pipeline_context_bundle(db: Session, creative_request_id: int) -> dict:
    resolved = get_latest_resolved_spec_for_request(db, creative_request_id)
    if not resolved:
        raise ValueError("Resolved creative spec not found")

    media_inputs = get_creative_media_inputs(db, creative_request_id)

    return {
        "provider": resolved.provider,
        "workflow": _normalize_workflow(resolved),
        "generation_mode": _normalize_generation_mode(resolved.generation_mode),
        "prompt_text": resolved.prompt_text,
        "negative_prompt": resolved.negative_prompt,
        "voiceover_script": resolved.voiceover_script,
        "caption_text": resolved.caption_text,
        "hashtags": resolved.hashtags,
        "provider_payload_json": resolved.provider_payload_json or {},
        "media_inputs": [
            {
                "media_role": media.media_role,
                "storage_type": media.storage_type,
                "storage_key": media.storage_key,
                "media_url": media.media_url,
                "mime_type": media.mime_type,
                "is_primary": media.is_primary,
            }
            for media in media_inputs
        ],
    }
