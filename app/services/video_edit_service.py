from sqlalchemy.orm import Session

from app.pg_tables import CreativeRequest
from app.schemas import CreativeRequestCreate
from app.services.creative_request_service import (
    get_creative_media_inputs,
    get_latest_resolved_spec_for_request,
)
from app.services.prompt_intake_service import intake_and_resolve_creative_request


def _merge_media_inputs(original_media_inputs, replacement_media_inputs, keep_source_image: bool):
    merged = []

    if keep_source_image:
        for media in original_media_inputs:
            merged.append(
                {
                    "media_role": media.media_role,
                    "storage_type": media.storage_type,
                    "storage_key": media.storage_key,
                    "media_url": media.media_url,
                    "mime_type": media.mime_type,
                    "is_primary": media.is_primary,
                }
            )

    for media in replacement_media_inputs:
        merged.append(media.model_dump())

    return merged


def _build_shot_updates_payload(shot_updates):
    return [
        {
            "shot_number": shot.shot_number,
            "shot_name": shot.shot_name,
            "description": shot.description,
            "camera_move": shot.camera_move,
            "duration_seconds": shot.duration_seconds,
            "transition_style": shot.transition_style,
        }
        for shot in shot_updates
    ]


def create_edit_revision_from_creative_request(db: Session, payload):
    original_request = db.get(CreativeRequest, payload.creative_request_id)
    if not original_request:
        raise ValueError("Original creative request not found")

    original_media_inputs = get_creative_media_inputs(db, payload.creative_request_id)
    original_resolved_spec = get_latest_resolved_spec_for_request(db, payload.creative_request_id)

    merged_media_inputs = _merge_media_inputs(
        original_media_inputs=original_media_inputs,
        replacement_media_inputs=payload.replacement_media_inputs,
        keep_source_image=payload.keep_source_image,
    )

    original_raw_input_json = original_request.raw_input_json or {}

    edit_layer = {
        "edit_request": {
            "edit_goal": payload.edit_goal,
            "edit_notes": payload.edit_notes,
            "change_hook": payload.change_hook,
            "change_cta": payload.change_cta,
            "change_tone": payload.change_tone,
            "change_visual_style": payload.change_visual_style,
            "change_environment_style": payload.change_environment_style,
            "change_lighting_style": payload.change_lighting_style,
            "change_camera_style": payload.change_camera_style,
            "change_motion_intensity": payload.change_motion_intensity,
            "add_music": payload.add_music,
            "music_mode": payload.music_mode,
            "music_track_name": payload.music_track_name,
            "music_mood": payload.music_mood,
            "music_notes": payload.music_notes,
            "shot_updates": _build_shot_updates_payload(payload.shot_updates),
            "original_resolved_spec": {
                "provider": original_resolved_spec.provider if original_resolved_spec else None,
                "workflow": original_resolved_spec.workflow if original_resolved_spec else None,
                "generation_mode": original_resolved_spec.generation_mode if original_resolved_spec else None,
                "prompt_text": original_resolved_spec.prompt_text if original_resolved_spec else None,
                "caption_text": original_resolved_spec.caption_text if original_resolved_spec else None,
            },
        }
    }

    merged_raw_input_json = {
        **original_raw_input_json,
        **edit_layer,
    }

    creative_request_payload = CreativeRequestCreate(
        client_id=original_request.client_id,
        campaign_id=original_request.campaign_id,
        content_idea_id=original_request.content_idea_id,
        request_source="edit_revision",
        content_goal=original_request.content_goal,
        content_type=original_request.content_type,
        target_platform=original_request.target_platform,
        generation_mode=original_request.generation_mode,
        preferred_workflow=payload.regenerate_workflow or original_request.preferred_workflow,
        topic=payload.change_hook or original_request.topic,
        hook=payload.change_hook or original_request.hook,
        angle=original_request.angle,
        description=original_request.description,
        cta=payload.change_cta or original_request.cta,
        tone=payload.change_tone or original_request.tone,
        audience=original_request.audience,
        visual_style=payload.change_visual_style or original_request.visual_style,
        scene_description=payload.edit_notes or original_request.scene_description,
        extra_instructions=payload.music_notes or original_request.extra_instructions,
        raw_input_json=merged_raw_input_json,
        media_inputs=merged_media_inputs,
    )

    return intake_and_resolve_creative_request(db, creative_request_payload)
