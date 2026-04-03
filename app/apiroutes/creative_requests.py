from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import CreativeRequestCreate, CreativeRequestResponse
from app.services.creative_request_service import get_creative_request
from app.services.prompt_intake_service import intake_and_resolve_creative_request
from app.services.prompt_resolution_service import resolve_creative_request
from app.services.pipeline_bridge_service import (
    build_existing_pipeline_payload_from_creative_request,
    build_pipeline_context_bundle,
)
from app.services.pipeline_execution_service import run_creative_request_through_existing_pipeline

router = APIRouter(prefix="/creative-requests", tags=["creative-requests"])


@router.post("", response_model=CreativeRequestResponse)
def create_creative_request_route(payload: CreativeRequestCreate, db: Session = Depends(get_db)):
    result = intake_and_resolve_creative_request(db, payload)
    return result["creative_request"]


@router.get("/{creative_request_id}")
def get_creative_request_route(creative_request_id: int, db: Session = Depends(get_db)):
    creative_request = get_creative_request(db, creative_request_id)
    if not creative_request:
        raise HTTPException(status_code=404, detail="Creative request not found")
    return creative_request


@router.post("/{creative_request_id}/resolve")
def resolve_creative_request_route(creative_request_id: int, db: Session = Depends(get_db)):
    try:
        return resolve_creative_request(db, creative_request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{creative_request_id}/pipeline-payload")
def get_existing_pipeline_payload_route(creative_request_id: int, db: Session = Depends(get_db)):
    try:
        return build_existing_pipeline_payload_from_creative_request(db, creative_request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{creative_request_id}/pipeline-context")
def get_pipeline_context_route(creative_request_id: int, db: Session = Depends(get_db)):
    try:
        return build_pipeline_context_bundle(db, creative_request_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{creative_request_id}/run")
def run_creative_request_route(creative_request_id: int, db: Session = Depends(get_db)):
    try:
        return run_creative_request_through_existing_pipeline(db, creative_request_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
