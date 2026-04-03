from datetime import datetime, UTC
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.pg_tables import Approval, ContentIdea
from app.schemas import ApprovalResponse, ApprovalUpdate

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/content-ideas/{content_idea_id}", response_model=ApprovalResponse)
def create_or_get_approval(content_idea_id: int, db: Session = Depends(get_db)):
    content_idea = db.get(ContentIdea, content_idea_id)
    if not content_idea:
        raise HTTPException(status_code=404, detail="Content idea not found")

    existing = db.query(Approval).filter(Approval.content_idea_id == content_idea_id).first()
    if existing:
        return existing

    approval = Approval(content_idea_id=content_idea_id, status="pending")
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval


@router.put("/content-ideas/{content_idea_id}", response_model=ApprovalResponse)
def update_approval(content_idea_id: int, payload: ApprovalUpdate, db: Session = Depends(get_db)):
    approval = db.query(Approval).filter(Approval.content_idea_id == content_idea_id).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")

    approval.status = payload.status
    approval.feedback = payload.feedback
    approval.approved_by = payload.approved_by

    if payload.status == "approved":
        approval.approved_at = datetime.now(UTC)

    db.commit()
    db.refresh(approval)
    return approval
