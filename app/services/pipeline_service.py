from app.pg_tables import (
    Campaign,
    ContentIdea,
    Script,
    VideoPrompt,
)
from app.services.asset_generator import generate_asset_from_video_prompt
from app.services.content_generator import (
    generate_script_from_idea,
    generate_video_prompt_from_script,
)
from app.services.resolved_spec_lookup_service import get_prompt_override_bundle_for_content_idea


class PipelineError(Exception):
    pass


class AssetGenerationPayload:
    def __init__(
        self,
        content_idea_id: int,
        prompt_text: str,
        source_image_s3_key: str | None = None,
        generation_mode: str = "image_to_video",
        logo_s3_key: str | None = None,
    ):
        self.content_idea_id = content_idea_id
        self.prompt_text = prompt_text
        self.source_image_s3_key = source_image_s3_key
        self.generation_mode = generation_mode
        self.logo_s3_key = logo_s3_key


def _normalize_text(value, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value).strip()


def _get_provider_payload_json(prompt_override: dict | None) -> dict:
    if not prompt_override:
        return {}
    return prompt_override.get("provider_payload_json") or {}


def build_higgsfield_prompt(
    base_prompt_text: str,
    negative_prompt: str | None = None,
    provider_payload_json: dict | None = None,
) -> str:
    provider_payload_json = provider_payload_json or {}

    base_prompt = _normalize_text(base_prompt_text)
    negative_prompt = _normalize_text(negative_prompt)

    visual_style_override = _normalize_text(provider_payload_json.get("visual_style_override"))
    camera_style = _normalize_text(provider_payload_json.get("camera_style"))
    motion_intensity = _normalize_text(provider_payload_json.get("motion_intensity"))
    environment_style = _normalize_text(provider_payload_json.get("environment_style"))
    lighting_style = _normalize_text(provider_payload_json.get("lighting_style"))

    preserve_environment = provider_payload_json.get("preserve_environment")
    preserve_identity = provider_payload_json.get("preserve_identity")
    use_source_image_strongly = provider_payload_json.get("use_source_image_strongly")

    prompt_parts = [base_prompt]

    style_lines = []
    if visual_style_override:
        style_lines.append(f"Visual style: {visual_style_override}.")
    if camera_style:
        style_lines.append(f"Camera style: {camera_style}.")
    if motion_intensity:
        style_lines.append(f"Motion intensity: {motion_intensity}.")
    if environment_style:
        style_lines.append(f"Environment style: {environment_style}.")
    if lighting_style:
        style_lines.append(f"Lighting style: {lighting_style}.")

    if style_lines:
        prompt_parts.append("\n".join(style_lines))

    constraints = []

    if preserve_identity is not False:
        constraints.append("Preserve facial identity and subject likeness.")
    if preserve_environment is True:
        constraints.append("Maintain strong environmental continuity from the source image where appropriate.")
    if use_source_image_strongly is True:
        constraints.append("Use the source image strongly as the visual anchor for the generated motion.")
    constraints.append("Keep the subject realistic and professional.")
    constraints.append("Avoid distortions, unrealistic motion, and visual artifacts.")
    constraints.append("Create polished, social-media-ready cinematic quality.")

    prompt_parts.append("Constraints:\n- " + "\n- ".join(constraints))

    if negative_prompt:
        prompt_parts.append(f"Negative prompt guidance: {negative_prompt}")

    provider_prompt = "\n\n".join(part for part in prompt_parts if part).strip()
    return provider_prompt[:1000]


def _get_or_create_script(db, content_idea_id: int, content_idea, campaign):
    script = (
        db.query(Script)
        .filter(Script.content_idea_id == content_idea_id)
        .first()
    )

    if script:
        return script

    generated_script = generate_script_from_idea(
        content_idea=content_idea,
        campaign=campaign,
    )
    script = Script(
        content_idea_id=content_idea_id,
        hook=generated_script["hook"],
        script_text=generated_script["script_text"],
        caption=generated_script["caption"],
        hashtags=generated_script["hashtags"],
        voiceover_text=generated_script["voiceover_text"],
    )
    db.add(script)
    db.commit()
    db.refresh(script)
    return script


def _get_or_create_video_prompt(db, content_idea_id: int, content_idea, campaign, script):
    video_prompt = (
        db.query(VideoPrompt)
        .filter(VideoPrompt.content_idea_id == content_idea_id)
        .first()
    )

    if video_prompt:
        return video_prompt

    generated_video_prompt = generate_video_prompt_from_script(
        content_idea=content_idea,
        campaign=campaign,
        script=script,
    )
    video_prompt = VideoPrompt(
        content_idea_id=content_idea_id,
        prompt_text=generated_video_prompt["prompt_text"],
        shot_list=generated_video_prompt["shot_list"],
        visual_style=generated_video_prompt["visual_style"],
        camera_notes=generated_video_prompt["camera_notes"],
    )
    db.add(video_prompt)
    db.commit()
    db.refresh(video_prompt)
    return video_prompt


def run_content_pipeline(
    content_idea_id: int,
    source_image_s3_key: str | None = None,
    generation_mode: str | None = None,
    db=None,
):
    if db is None:
        raise PipelineError("Database session is required")

    content_idea = db.get(ContentIdea, content_idea_id)
    if not content_idea:
        raise PipelineError("Content idea not found")

    campaign = db.get(Campaign, content_idea.campaign_id)
    if not campaign:
        raise PipelineError("Campaign not found")

    script = _get_or_create_script(
        db=db,
        content_idea_id=content_idea_id,
        content_idea=content_idea,
        campaign=campaign,
    )

    video_prompt = _get_or_create_video_prompt(
        db=db,
        content_idea_id=content_idea_id,
        content_idea=content_idea,
        campaign=campaign,
        script=script,
    )

    prompt_override = get_prompt_override_bundle_for_content_idea(db, content_idea_id)
    provider_payload_json = _get_provider_payload_json(prompt_override)

    base_prompt_text = (
        _normalize_text(prompt_override.get("prompt_text"))
        if prompt_override and prompt_override.get("prompt_text")
        else _normalize_text(video_prompt.prompt_text)
    )

    if not base_prompt_text:
        raise PipelineError("Base prompt is empty")

    negative_prompt = (
        _normalize_text(prompt_override.get("negative_prompt"))
        if prompt_override and prompt_override.get("negative_prompt")
        else ""
    )

    caption_used = (
        _normalize_text(prompt_override.get("caption_text"))
        if prompt_override and prompt_override.get("caption_text")
        else _normalize_text(script.caption)
    )

    request_generation_mode = _normalize_text(generation_mode)

    override_generation_mode = (
        _normalize_text(prompt_override.get("generation_mode"))
        if prompt_override and prompt_override.get("generation_mode")
        else ""
    )

    final_generation_mode = request_generation_mode or override_generation_mode

    if not final_generation_mode:
        final_generation_mode = (
            "image_to_video" if _normalize_text(source_image_s3_key) else "text_to_image"
        )

    if final_generation_mode not in {"image_to_video", "text_to_image"}:
        raise PipelineError(f"Unsupported generation_mode: {final_generation_mode}")

    if final_generation_mode == "image_to_video" and not _normalize_text(source_image_s3_key):
        raise PipelineError("source_image_s3_key is required for image_to_video")

    logo_s3_key = (
        _normalize_text(provider_payload_json.get("logo_s3_key"))
        or _normalize_text(getattr(campaign, "logo_s3_key", None))
    )

    higgsfield_prompt = build_higgsfield_prompt(
        base_prompt_text=base_prompt_text,
        negative_prompt=negative_prompt,
        provider_payload_json=provider_payload_json,
    )

    payload = AssetGenerationPayload(
        content_idea_id=content_idea_id,
        prompt_text=higgsfield_prompt,
        source_image_s3_key=source_image_s3_key,
        generation_mode=final_generation_mode,
        logo_s3_key=logo_s3_key or None,
    )

    asset = generate_asset_from_video_prompt(payload, db)
    if not asset:
        raise PipelineError("Failed to generate asset")

    asset.status = "generated"
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return {
        "workflow": "higgsfield",
        "content_idea_id": content_idea_id,
        "script_id": script.id,
        "video_prompt_id": video_prompt.id,
        "generated_asset_id": asset.id,
        "published_post_id": None,
        "publish_status": None,
        "asset_url": asset.asset_url,
        "asset_type": asset.asset_type,
        "generation_mode": final_generation_mode,
        "caption_used": caption_used,
        "review_status": asset.status,
    }
