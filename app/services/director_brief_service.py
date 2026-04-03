from app.schemas import CreativeRequestCreate


def build_creative_request_from_director_brief(payload):
    raw_input_json = {
        "director_brief": {
            "environment_style": payload.environment_style,
            "lighting_style": payload.lighting_style,
            "camera_style": payload.camera_style,
            "motion_intensity": payload.motion_intensity,
            "preserve_environment": payload.preserve_environment,
            "preserve_identity": payload.preserve_identity,
            "use_source_image_strongly": payload.use_source_image_strongly,
            "voiceover_required": payload.voiceover_required,
            "short_form_hook_priority": payload.short_form_hook_priority,
            "safe_text_overlay_regions": payload.safe_text_overlay_regions,
            "direction_notes": payload.direction_notes,
            "negative_direction": payload.negative_direction,
            "requested_shots": [
                {
                    "shot_name": shot.shot_name,
                    "description": shot.description,
                    "camera_move": shot.camera_move,
                    "duration_seconds": shot.duration_seconds,
                    "transition_style": shot.transition_style,
                }
                for shot in payload.requested_shots
            ],
        }
    }

    return CreativeRequestCreate(
        client_id=payload.client_id,
        campaign_id=payload.campaign_id,
        content_idea_id=payload.content_idea_id,
        request_source="director_brief",
        content_goal=payload.content_goal,
        content_type=payload.content_type,
        target_platform=payload.target_platform,
        generation_mode=payload.generation_mode,
        preferred_workflow=payload.preferred_workflow,
        topic=payload.topic,
        hook=payload.hook,
        angle=payload.angle,
        description=payload.description,
        cta=payload.cta,
        tone=payload.tone,
        audience=payload.audience,
        visual_style=payload.visual_style,
        scene_description=payload.direction_notes,
        extra_instructions=payload.negative_direction,
        raw_input_json=raw_input_json,
        media_inputs=payload.media_inputs,
    )
