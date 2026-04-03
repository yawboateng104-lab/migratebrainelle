# app/services/cinematic_pipeline_service.py
import base64
import mimetypes
import tempfile
import uuid
from pathlib import Path

import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.integrations.elevenlabs_tts import synthesize_speech_to_file
from app.integrations.runway import (
    generate_image_to_video,
    wait_for_video_completion,
)
from app.integrations.s3 import upload_file_to_s3
from app.pg_tables import GeneratedAsset, PublishedPost
from app.services.download_service import download_file
from app.services.video_merge_service import (
    concatenate_videos,
    create_thumbnail,
    merge_video_with_voiceover,
)


DEFAULT_SHOT_1_PROMPT = """
Subject: Confident female CEO

Scene: Luxurious high-rise executive office with floor-to-ceiling glass windows overlooking a modern city skyline at sunset

Lighting: Warm golden hour sunlight, cinematic lighting, soft shadows, natural highlights

Camera: Slow cinematic dolly-in shot

Motion: Subtle hair and clothing movement from ambient airflow, natural blinking, micro facial expressions

Environment: Elegant, modern, minimalist, polished surfaces, high-end decor

Background: City lights gradually turning on with realistic reflections on glass

Style: Ultra-realistic, photorealistic, 4K, shallow depth of field, bokeh, HDR, professional color grading, luxury corporate aesthetic

Mood: Inspirational, powerful, aspirational leadership energy
Lens: 85mm cinematic lens

Constraints: Preserve facial identity, maintain likeness, no facial distortion, natural skin tone
""".strip()


DEFAULT_SHOT_2_PROMPT = """
Subject: Confident female CEO

Scene: Premium executive office with elegant city skyline backdrop at sunset

Lighting: Warm cinematic golden hour tones with soft shadows and polished highlights

Camera: Slow cinematic push-in with slightly wider framing

Motion: Subtle posture adjustment, natural blinking, slight facial expression changes, gentle movement in hair and clothing

Environment: Modern luxury office, clean minimalist styling, refined decor, strong corporate presence

Background: City lights softly glowing with realistic window reflections and depth

Style: Ultra-realistic, photorealistic, shallow depth of field, bokeh, HDR, luxury corporate brand aesthetic, professionally color graded

Mood: Inspirational, commanding, polished, high-status leadership energy

Constraints: Preserve facial identity, maintain likeness, no facial distortion, natural skin tone
""".strip()


def _image_url_to_data_uri(image_url: str) -> str:
    response = requests.get(image_url, timeout=120)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type")
    if not content_type:
        guessed_type, _ = mimetypes.guess_type(image_url)
        content_type = guessed_type or "image/png"

    encoded = base64.b64encode(response.content).decode("utf-8")
    return f"data:{content_type};base64,{encoded}"


def run_cinematic_pipeline(
    db: Session,
    content_idea_id: int,
    source_image_url: str,
    script_text: str,
    caption_text: str,
    shot_1_prompt: str,
    shot_2_prompt: str,
    voice_id: str | None = None,
) -> dict:
    """
    Generate a cinematic reel:
    - Runway shot 1
    - Runway shot 2
    - ElevenLabs voiceover
    - ffmpeg stitch + merge
    - upload final MP4 + thumbnail to S3
    - save generated_assets row
    """
    run_id = str(uuid.uuid4())
    temp_dir = Path(tempfile.gettempdir()) / "cinematic_pipeline" / run_id
    temp_dir.mkdir(parents=True, exist_ok=True)

    runway_image_input = _image_url_to_data_uri(source_image_url)

    resolved_shot_1_prompt = (
        shot_1_prompt.strip()
        if shot_1_prompt and shot_1_prompt.strip()
        else DEFAULT_SHOT_1_PROMPT
    )
    resolved_shot_2_prompt = (
        shot_2_prompt.strip()
        if shot_2_prompt and shot_2_prompt.strip()
        else DEFAULT_SHOT_2_PROMPT
    )

    # 1) Runway shot 1
    shot1_task = generate_image_to_video(
        image_url=runway_image_input,
        prompt_text=resolved_shot_1_prompt,
        duration_seconds=8,
        ratio="720:1280",
    )
    shot1_final = wait_for_video_completion(task_id=shot1_task["id"])
    shot1_url = shot1_final["output"][0]
    shot1_local = download_file(shot1_url, str(temp_dir / "shot1.mp4"))

    # 2) Runway shot 2
    shot2_task = generate_image_to_video(
        image_url=runway_image_input,
        prompt_text=resolved_shot_2_prompt,
        duration_seconds=8,
        ratio="720:1280",
    )
    shot2_final = wait_for_video_completion(task_id=shot2_task["id"])
    shot2_url = shot2_final["output"][0]
    shot2_local = download_file(shot2_url, str(temp_dir / "shot2.mp4"))

    # 3) ElevenLabs narration
    voiceover_local = synthesize_speech_to_file(
        text=script_text,
        output_path=temp_dir / "voiceover.mp3",
        voice_id=voice_id,
    )

    # 4) Stitch shots
    stitched_local = concatenate_videos(
        input_video_paths=[shot1_local, shot2_local],
        output_video_path=str(temp_dir / "stitched.mp4"),
    )

    # 5) Merge stitched video + narration
    final_local = merge_video_with_voiceover(
        input_video_path=stitched_local,
        voiceover_audio_path=voiceover_local,
        output_video_path=str(temp_dir / "final.mp4"),
    )

    # 6) Thumbnail
    thumb_local = create_thumbnail(
        input_video_path=final_local,
        output_image_path=str(temp_dir / "thumb.jpg"),
        timestamp_seconds=1,
    )

    # 7) Upload to S3
    final_s3_key = f"video-folder/content-idea-{content_idea_id}/{uuid.uuid4()}.mp4"
    thumb_s3_key = f"video-folder/content-idea-{content_idea_id}/{uuid.uuid4()}.jpg"

    final_upload = upload_file_to_s3(
        final_local,
        final_s3_key,
        content_type="video/mp4",
    )
    thumb_upload = upload_file_to_s3(
        thumb_local,
        thumb_s3_key,
        content_type="image/jpeg",
    )

    final_asset_url = final_upload["url"]
    thumbnail_url = thumb_upload["url"]

    # 8) Save generated asset
    generated_asset = GeneratedAsset(
        content_idea_id=content_idea_id,
        provider=settings.VIDEO_PROVIDER,
        asset_url=final_asset_url,
        thumbnail_url=thumbnail_url,
        asset_type="video",
        status="generated",
    )
    db.add(generated_asset)
    db.commit()
    db.refresh(generated_asset)

    return {
        "content_idea_id": content_idea_id,
        "generated_asset_id": generated_asset.id,
        "asset_url": final_asset_url,
        "thumbnail_url": thumbnail_url,
        "caption_used": caption_text,
        "runway_shot_1_task_id": shot1_task["id"],
        "runway_shot_2_task_id": shot2_task["id"],
        "voice_provider": settings.VOICE_PROVIDER,
        "video_provider": settings.VIDEO_PROVIDER,
    }
