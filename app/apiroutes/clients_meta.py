from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ClientMetaConnectCreate
from app.services.meta_onboarding_service import create_client_meta_connection, get_client_meta_connections

router = APIRouter(prefix="/clients-meta", tags=["clients-meta"])


@router.post("")
def create_client_meta_connection_route(payload: ClientMetaConnectCreate, db: Session = Depends(get_db)):
    return create_client_meta_connection(db, payload)


@router.get("/clients/{client_id}")
def get_client_meta_connections_route(client_id: int, db: Session = Depends(get_db)):
    return get_client_meta_connections(db, client_id)
