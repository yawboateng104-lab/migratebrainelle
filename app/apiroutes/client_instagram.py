from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.client_instagram_update_service import (
    ClientInstagramUpdateError,
    upsert_client_instagram_account,
)

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("/{client_id}/instagram/connect")
def connect_instagram(
    client_id: int,
    payload: dict,
    db: Session = Depends(get_db),
):
    try:
        return upsert_client_instagram_account(
            client_id=client_id,
            instagram_account_id=payload.get("instagram_account_id"),
            access_token=payload.get("access_token"),
            facebook_page_id=payload.get("facebook_page_id"),
            instagram_username=payload.get("instagram_username"),
            graph_base_url=payload.get(
                "graph_base_url",
                "https://graph.facebook.com/v25.0",
            ),
            token_expires_at=payload.get("token_expires_at"),
            db=db,
        )
    except ClientInstagramUpdateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
