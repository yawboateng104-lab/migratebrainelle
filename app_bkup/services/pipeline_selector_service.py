# app/services/pipeline_selector_service.py
from app.services.pipeline_service import run_content_pipeline as run_higgsfield_pipeline
from app.services.pipeline_service2 import run_content_pipeline as run_runway_pipeline


class WorkflowSelectorError(Exception):
    pass


SUPPORTED_WORKFLOWS = {
    "higgsfield": run_higgsfield_pipeline,
    "runway_cinematic": run_runway_pipeline,
}


def run_selected_pipeline(
    workflow: str,
    content_idea_id: int,
    source_image_s3_key: str,
    db,
):
    selected_workflow = (workflow or "").strip().lower()

    pipeline_func = SUPPORTED_WORKFLOWS.get(selected_workflow)
    if not pipeline_func:
        raise WorkflowSelectorError(
            f"Unsupported workflow '{workflow}'. "
            f"Supported workflows: {', '.join(SUPPORTED_WORKFLOWS.keys())}"
        )

    result = pipeline_func(
        content_idea_id=content_idea_id,
        source_image_s3_key=source_image_s3_key,
        db=db,
    )

    return {
        "workflow": selected_workflow,
        "result": result,
    }
