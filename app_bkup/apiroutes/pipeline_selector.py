# app/apiroutes/pipeline_selector.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.pipeline_selector_service import (
    WorkflowSelectorError,
    run_selected_pipeline,
)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class PipelineRunRequest(BaseModel):
    workflow: str
    source_image_s3_key: str


@router.post("/content-ideas/{content_idea_id}/run")
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
            db=db,
        )
    except WorkflowSelectorError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
