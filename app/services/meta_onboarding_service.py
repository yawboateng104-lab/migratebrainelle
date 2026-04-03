from sqlalchemy.orm import Session

from app.pg_tables import ClientInstagramAccount


def create_client_meta_connection(db: Session, payload):
    record = ClientInstagramAccount(
        client_id=payload.client_id,
        facebook_page_id=payload.facebook_page_id,
        page_name=payload.page_name,
        instagram_account_id=payload.instagram_account_id,
        instagram_username=payload.instagram_username,
        access_token=payload.access_token,
        token_expires_at=payload.token_expires_at,
        is_active=(payload.status or "active") == "active",
        is_primary=payload.is_primary,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_client_meta_connections(db: Session, client_id: int):
    return (
        db.query(ClientInstagramAccount)
        .filter(ClientInstagramAccount.client_id == client_id)
        .order_by(ClientInstagramAccount.id.desc())
        .all()
    )
