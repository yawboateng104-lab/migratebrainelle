from __future__ import annotations

from sqlalchemy.orm import Session

from app.pg_tables import ContentIdea
from app.services.pipeline_service import run_content_pipeline as run_higgsfield_pipeline
from app.services.pipeline_service2 import run_content_pipeline as run_runway_pipeline


SUPPORTED_WORKFLOWS = {
    "higgsfield": run_higgsfield_pipeline,
    "runway_cinematic": run_runway_pipeline,
}


class WorkflowSelectorError(Exception):
    pass


def _get_content_idea_or_raise(db: Session, content_idea_id: int) -> ContentIdea:
    content_idea = db.get(ContentIdea, content_idea_id)
    if not content_idea:
        raise WorkflowSelectorError(f"Content idea {content_idea_id} not found")
    return content_idea


def _get_pipeline_runner_or_raise(workflow: str):
    normalized_workflow = (workflow or "").strip()

    if not normalized_workflow:
        raise WorkflowSelectorError("Workflow is required")

    runner = SUPPORTED_WORKFLOWS.get(normalized_workflow)
    if not runner:
        supported = ", ".join(sorted(SUPPORTED_WORKFLOWS.keys()))
        raise WorkflowSelectorError(
            f"Unsupported workflow '{normalized_workflow}'. Supported workflows: {supported}"
        )

    return runner


def run_selected_pipeline(
    db: Session,
    content_idea_id: int,
    workflow: str,
    source_image_s3_key: str | None = None,
    generation_mode: str | None = None,
):
    """
    Runs the selected provider workflow for a content idea.
    """

    _get_content_idea_or_raise(db, content_idea_id)
    runner = _get_pipeline_runner_or_raise(workflow)

    return runner(
        content_idea_id=content_idea_id,
        source_image_s3_key=source_image_s3_key,
        generation_mode=generation_mode,
        db=db,
    )
