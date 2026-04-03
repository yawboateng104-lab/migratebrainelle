from urllib.parse import urlparse

from app.config import settings
from app.integrations.s3 import generate_presigned_get_url
from app.pg_tables import (
    Approval,
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


def run_content_pipeline(content_idea_id: int, source_image_s3_key: str, db):
    content_idea = db.get(ContentIdea, content_idea_id)
    if not content_idea:
        raise PipelineError("Content idea not found")

    campaign = db.get(Campaign, content_idea.campaign_id)
    if not campaign:
        raise PipelineError("Campaign not found")

    approval = (
        db.query(Approval)
        .filter(Approval.content_idea_id == content_idea_id)
        .first()
    )
    if not approval or approval.status != "approved":
        raise PipelineError("Content idea must be approved before running pipeline")

    script = (
        db.query(Script)
        .filter(Script.content_idea_id == content_idea_id)
        .first()
    )
    if not script:
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

    video_prompt = (
        db.query(VideoPrompt)
        .filter(VideoPrompt.content_idea_id == content_idea_id)
        .first()
    )
    if not video_prompt:
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

    source_image_url = generate_presigned_get_url(
        bucket=settings.S3_BUCKET_NAME,
        key=source_image_s3_key,
        expires_in=3600,
    )

    base_prompt = (video_prompt.prompt_text or "").strip()[:600]

    shot_1_prompt = f"""
Enhance realism and cinematic quality of the subject.
Preserve the original environment.
Improve lighting, motion, and detail.

{base_prompt}
""".strip()[:1000]

    shot_2_prompt = f"""
{base_prompt}

Replace the background with a luxurious panoramic high-rise executive office.
Use warm golden hour cinematic lighting, realistic shadows, and a slow dolly-in camera move.
Ultra-realistic, photorealistic, luxury corporate aesthetic.
Preserve facial identity exactly.
""".strip()[:1000]

    cinematic_result = run_cinematic_pipeline(
        db=db,
        content_idea_id=content_idea_id,
        source_image_url=source_image_url,
        script_text=script.voiceover_text or script.script_text,
        caption_text=script.caption or "",
        shot_1_prompt=shot_1_prompt,
        shot_2_prompt=shot_2_prompt,
        voice_id=None,
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
        "caption_used": script.caption,
        "review_status": asset.status,
    }
