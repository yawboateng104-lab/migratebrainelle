from urllib.parse import urlparse

from app.config import settings
from app.integrations.s3 import generate_presigned_get_url
from app.pg_tables import (
    Campaign,
    ContentIdea,
    GeneratedAsset,
    Script,
    VideoPrompt,
)
from app.services.cinematic_pipeline_service import run_cinematic_pipeline
from app.services.content_generator import (
    generate_script_from_idea,
    generate_video_prompt_from_script,
)
from app.services.resolved_spec_lookup_service import get_prompt_override_bundle_for_content_idea


class PipelineError(Exception):
    pass


class AssetGenerationPayload:
    def __init__(self, content_idea_id: int, prompt_text: str, source_image_s3_key: str):
        self.content_idea_id = content_idea_id
        self.prompt_text = prompt_text
        self.source_image_s3_key = source_image_s3_key


def extract_s3_key_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path.lstrip("/")


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


def _normalize_text(value, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value).strip()


def _get_provider_payload_json(prompt_override: dict | None) -> dict:
    if not prompt_override:
        return {}
    return prompt_override.get("provider_payload_json") or {}


def _build_default_shot_prompts(base_prompt: str) -> list[dict]:
    shot_1 = {
        "shot_number": 1,
        "shot_name": "Primary realism shot",
        "prompt": f"""
{base_prompt}

Scene direction:
- Preserve subject identity and realism
- Preserve the strongest visual continuity from the source image
- Improve cinematic quality, lighting, detail, and natural motion
- Keep output polished and premium for short-form social media
""".strip()[:1000],
        "duration_seconds": 4,
        "camera_move": "subtle cinematic push-in",
        "transition_style": "straight cut",
    }

    shot_2 = {
        "shot_number": 2,
        "shot_name": "Elevated brand scene",
        "prompt": f"""
{base_prompt}

Second scene direction:
- Create a premium cinematic evolution of the story
- Use realistic environment styling appropriate to the prompt and client brand
- Preserve facial identity exactly
- Use smooth camera movement and polished high-end visual quality
- Social-media-ready, photorealistic output
""".strip()[:1000],
        "duration_seconds": 4,
        "camera_move": "slow pan",
        "transition_style": "match cut",
    }

    return [shot_1, shot_2]


def _get_shot_prompts(base_prompt: str, provider_payload_json: dict) -> list[dict]:
    shot_prompts = provider_payload_json.get("shot_prompts")

    if shot_prompts and isinstance(shot_prompts, list):
        cleaned = []
        for item in shot_prompts:
            if not isinstance(item, dict):
                continue

            prompt_text = _normalize_text(item.get("prompt"))
            if not prompt_text:
                continue

            cleaned.append(
                {
                    "shot_number": item.get("shot_number") or (len(cleaned) + 1),
                    "shot_name": _normalize_text(item.get("shot_name"), fallback=f"Shot {len(cleaned) + 1}"),
                    "prompt": prompt_text[:1000],
                    "duration_seconds": item.get("duration_seconds"),
                    "camera_move": _normalize_text(item.get("camera_move")),
                    "transition_style": _normalize_text(item.get("transition_style")),
                }
            )

        if cleaned:
            return cleaned

    return _build_default_shot_prompts(base_prompt)


def _select_runway_shots_for_current_executor(shot_prompts: list[dict]) -> tuple[str, str]:
    """
    Current cinematic pipeline takes shot_1_prompt and shot_2_prompt only.
    We stay future-ready by allowing many shots in resolved specs, but for now
    we pass the first two available shots to the current executor.
    """
    if not shot_prompts:
        raise PipelineError("No usable shot prompts were generated")

    shot_1_prompt = shot_prompts[0]["prompt"]

    if len(shot_prompts) >= 2:
        shot_2_prompt = shot_prompts[1]["prompt"]
    else:
        shot_2_prompt = shot_prompts[0]["prompt"]

    return shot_1_prompt, shot_2_prompt


def run_content_pipeline(content_idea_id: int, source_image_s3_key: str, db):
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

    base_prompt = (
        _normalize_text(prompt_override.get("prompt_text"))
        if prompt_override and prompt_override.get("prompt_text")
        else _normalize_text(video_prompt.prompt_text)
    )[:800]

    if not base_prompt:
        raise PipelineError("Base prompt is empty")

    voiceover_script = (
        _normalize_text(prompt_override.get("voiceover_script"))
        if prompt_override and prompt_override.get("voiceover_script")
        else _normalize_text(script.voiceover_text or script.script_text)
    )

    caption_text = (
        _normalize_text(prompt_override.get("caption_text"))
        if prompt_override and prompt_override.get("caption_text")
        else _normalize_text(script.caption)
    )

    voice_id = provider_payload_json.get("voice_id")
    shot_prompts = _get_shot_prompts(
        base_prompt=base_prompt,
        provider_payload_json=provider_payload_json,
    )
    shot_1_prompt, shot_2_prompt = _select_runway_shots_for_current_executor(shot_prompts)

    source_image_url = generate_presigned_get_url(
        bucket=settings.S3_BUCKET_NAME,
        key=source_image_s3_key,
        expires_in=3600,
    )

    cinematic_result = run_cinematic_pipeline(
        db=db,
        content_idea_id=content_idea_id,
        source_image_url=source_image_url,
        script_text=voiceover_script,
        caption_text=caption_text,
        shot_1_prompt=shot_1_prompt,
        shot_2_prompt=shot_2_prompt,
        voice_id=voice_id,
    )

    asset = db.get(GeneratedAsset, cinematic_result["generated_asset_id"])
    if not asset:
        raise PipelineError("Generated asset was not found after cinematic pipeline run")

    asset.status = "pending_review"
    db.add(asset)
    db.commit()
    db.refresh(asset)

    return {
        "workflow": "runway_cinematic",
        "content_idea_id": content_idea_id,
        "script_id": script.id,
        "video_prompt_id": video_prompt.id,
        "generated_asset_id": asset.id,
        "published_post_id": None,
        "publish_status": None,
        "asset_url": asset.asset_url,
        "caption_used": caption_text,
        "review_status": asset.status,
    }
