from datetime import UTC, datetime

from app.pg_tables import Client, ClientInstagramAccount


class ClientInstagramUpdateError(Exception):
    pass


def upsert_client_instagram_account(
    client_id: int,
    instagram_account_id: str,
    access_token: str,
    facebook_page_id: str | None,
    instagram_username: str | None,
    graph_base_url: str,
    token_expires_at=None,
    db=None,
):
    client = db.get(Client, client_id)
    if not client:
        raise ClientInstagramUpdateError("Client not found")

    # 🔍 check if IG account already exists
    existing_account = (
        db.query(ClientInstagramAccount)
        .filter(
            ClientInstagramAccount.instagram_account_id == instagram_account_id
        )
        .first()
    )

    if existing_account:
        # ✅ UPDATE EXISTING RECORD
        existing_account.client_id = client_id
        existing_account.access_token = access_token
        existing_account.facebook_page_id = facebook_page_id
        existing_account.instagram_username = instagram_username
        existing_account.graph_base_url = graph_base_url
        existing_account.token_expires_at = token_expires_at
        existing_account.token_obtained_at = datetime.now(UTC)
        existing_account.is_active = True

        db.add(existing_account)
        db.commit()
        db.refresh(existing_account)

        return {
            "client_id": client_id,
            "instagram_account_id": instagram_account_id,
            "status": "updated",
            "message": "Instagram token updated successfully",
        }

    # 🔄 deactivate old accounts for this client
    db.query(ClientInstagramAccount).filter(
        ClientInstagramAccount.client_id == client_id,
        ClientInstagramAccount.is_active == True,
    ).update({"is_active": False})

    # 🆕 insert new account
    new_account = ClientInstagramAccount(
        client_id=client_id,
        instagram_account_id=instagram_account_id,
        facebook_page_id=facebook_page_id,
        instagram_username=instagram_username,
        access_token=access_token,
        graph_base_url=graph_base_url,
        token_expires_at=token_expires_at,
        token_obtained_at=datetime.now(UTC),
        is_active=True,
    )

    db.add(new_account)
    db.commit()
    db.refresh(new_account)

    return {
        "client_id": client_id,
        "instagram_account_id": instagram_account_id,
        "status": "connected",
        "message": "Instagram account connected successfully",
    }
