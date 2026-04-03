from sqlalchemy.orm import Session

from app.pg_tables import CreativeRequest, ResolvedCreativeSpec


def get_latest_resolved_spec_for_content_idea(db: Session, content_idea_id: int):
    return (
        db.query(ResolvedCreativeSpec)
        .join(
            CreativeRequest,
            CreativeRequest.id == ResolvedCreativeSpec.creative_request_id,
        )
        .filter(CreativeRequest.content_idea_id == content_idea_id)
        .order_by(ResolvedCreativeSpec.id.desc())
        .first()
    )


def get_prompt_override_bundle_for_content_idea(db: Session, content_idea_id: int) -> dict | None:
    resolved = get_latest_resolved_spec_for_content_idea(db, content_idea_id)
    if not resolved:
        return None

    return {
        "provider": resolved.provider,
        "workflow": resolved.workflow,
        "generation_mode": resolved.generation_mode,
        "prompt_text": resolved.prompt_text,
        "negative_prompt": resolved.negative_prompt,
        "voiceover_script": resolved.voiceover_script,
        "caption_text": resolved.caption_text,
        "hashtags": resolved.hashtags,
        "provider_payload_json": resolved.provider_payload_json or {},
        "resolution_notes": resolved.resolution_notes,
    }
