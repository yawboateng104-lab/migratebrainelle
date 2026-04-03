from sqlalchemy.orm import Session

from app.services.creative_request_service import get_creative_request
from app.services.pipeline_bridge_service import (
    build_existing_pipeline_payload_from_creative_request,
    build_pipeline_context_bundle,
)
from app.services.pipeline_selector_service import run_selected_pipeline


def _normalize_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def run_creative_request_through_existing_pipeline(
    db: Session,
    creative_request_id: int,
):
    creative_request = get_creative_request(db, creative_request_id)
    if not creative_request:
        raise ValueError("Creative request not found")

    if not creative_request.content_idea_id:
        raise ValueError(
            "Creative request must be tied to a content_idea_id to use the current pipeline"
        )

    pipeline_payload = build_existing_pipeline_payload_from_creative_request(
        db=db,
        creative_request_id=creative_request_id,
    )
    if not isinstance(pipeline_payload, dict):
        raise ValueError("Pipeline bridge did not return a valid payload dictionary")

    execution_context = build_pipeline_context_bundle(
        db=db,
        creative_request_id=creative_request_id,
    )

    workflow = _normalize_text(pipeline_payload.get("workflow"))
    source_image_s3_key = _normalize_text(pipeline_payload.get("source_image_s3_key")) or None
    generation_mode = _normalize_text(pipeline_payload.get("generation_mode")) or None

    if not workflow:
        raise ValueError("Pipeline payload missing required 'workflow' value")

    if workflow == "image_to_video":
        raise ValueError(
            "Pipeline payload workflow was set to 'image_to_video'. "
            "That is a generation mode, not a supported workflow key. "
            "Expected something like 'higgsfield' or 'runway_cinematic'."
        )

    result = run_selected_pipeline(
        db=db,
        content_idea_id=creative_request.content_idea_id,
        workflow=workflow,
        source_image_s3_key=source_image_s3_key,
        generation_mode=generation_mode,
    )

    return {
        "creative_request_id": creative_request_id,
        "content_idea_id": creative_request.content_idea_id,
        "pipeline_payload": pipeline_payload,
        "execution_context": execution_context,
        "pipeline_result": result,
    }
