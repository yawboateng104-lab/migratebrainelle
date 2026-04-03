from sqlalchemy.orm import Session

from app.pg_tables import CreativeRequest, CreativeMediaInput, ResolvedCreativeSpec


def create_creative_request(db: Session, payload) -> CreativeRequest:
    creative_request = CreativeRequest(
        client_id=payload.client_id,
        campaign_id=payload.campaign_id,
        content_idea_id=payload.content_idea_id,
        request_source=payload.request_source,
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
        scene_description=payload.scene_description,
        extra_instructions=payload.extra_instructions,
        raw_input_json=payload.raw_input_json,
        status="pending",
    )
    db.add(creative_request)
    db.flush()

    for media in payload.media_inputs:
        db.add(
            CreativeMediaInput(
                creative_request_id=creative_request.id,
                media_role=media.media_role,
                storage_type=media.storage_type,
                storage_key=media.storage_key,
                media_url=media.media_url,
                mime_type=media.mime_type,
                is_primary=media.is_primary,
            )
        )

    db.commit()
    db.refresh(creative_request)
    return creative_request


def get_creative_request(db: Session, creative_request_id: int):
    return db.query(CreativeRequest).filter(CreativeRequest.id == creative_request_id).first()


def get_creative_media_inputs(db: Session, creative_request_id: int):
    return (
        db.query(CreativeMediaInput)
        .filter(CreativeMediaInput.creative_request_id == creative_request_id)
        .all()
    )


def create_resolved_spec(db: Session, creative_request_id: int, client_id: int, spec: dict):
    resolved = ResolvedCreativeSpec(
        creative_request_id=creative_request_id,
        client_id=client_id,
        provider=spec["provider"],
        workflow=spec["workflow"],
        generation_mode=spec["generation_mode"],
        prompt_text=spec["prompt_text"],
        negative_prompt=spec.get("negative_prompt"),
        voiceover_script=spec.get("voiceover_script"),
        caption_text=spec.get("caption_text"),
        hashtags=spec.get("hashtags"),
        provider_payload_json=spec.get("provider_payload_json"),
        resolution_notes=spec.get("resolution_notes"),
        status="resolved",
    )
    db.add(resolved)
    db.commit()
    db.refresh(resolved)
    return resolved


def get_latest_resolved_spec_for_request(db: Session, creative_request_id: int):
    return (
        db.query(ResolvedCreativeSpec)
        .filter(ResolvedCreativeSpec.creative_request_id == creative_request_id)
        .order_by(ResolvedCreativeSpec.id.desc())
        .first()
    )
