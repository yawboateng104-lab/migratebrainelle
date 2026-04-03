from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import (
    ApproveAndPublishResponse,
    PipelineRunRequest,
    PipelineRunResponse,
    RejectAssetResponse,
)
from app.services.pipeline_selector_service import (
    WorkflowSelectorError,
    run_selected_pipeline,
)
from app.services.review_service import (
    ReviewError,
    approve_and_publish_generated_asset,
    reject_generated_asset,
)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/content-ideas/{content_idea_id}/run", response_model=PipelineRunResponse)
def run_pipeline(
    content_idea_id: int,
    payload: PipelineRunRequest,
    db: Session = Depends(get_db),
):
    try:
        return run_selected_pipeline(
            workflow=payload.workflow,
            content_idea_id=content_idea_id,
            source_image_s3_key=payload.source_image_s3_key,
            generation_mode=payload.generation_mode,
            db=db,
        )
    except WorkflowSelectorError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc




@router.post(
    "/generated-assets/{generated_asset_id}/approve-and-publish",
    response_model=ApproveAndPublishResponse,
)
def approve_and_publish_pipeline_asset(
    generated_asset_id: int,
    db: Session = Depends(get_db),
):
    try:
        return approve_and_publish_generated_asset(
            generated_asset_id=generated_asset_id,
            db=db,
        )
    except ReviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post(
    "/generated-assets/{generated_asset_id}/reject",
    response_model=RejectAssetResponse,
)
def reject_pipeline_asset(
    generated_asset_id: int,
    db: Session = Depends(get_db),
):
    try:
        return reject_generated_asset(
            generated_asset_id=generated_asset_id,
            db=db,
        )
    except ReviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
