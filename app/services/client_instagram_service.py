from datetime import UTC, datetime

from app.pg_tables import Campaign, ContentIdea, ClientInstagramAccount


class ClientInstagramError(Exception):
    pass


def _is_token_expired(token_expires_at) -> bool:
    if not token_expires_at:
        return False

    now = datetime.now(UTC)

    if token_expires_at.tzinfo is None:
        token_expires_at = token_expires_at.replace(tzinfo=UTC)

    return token_expires_at <= now


def get_instagram_credentials_for_content_idea(content_idea_id: int, db) -> dict:
    content_idea = db.get(ContentIdea, content_idea_id)
    if not content_idea:
        raise ClientInstagramError("Content idea not found")

    campaign = db.get(Campaign, content_idea.campaign_id)
    if not campaign:
        raise ClientInstagramError("Campaign not found")

    client_id = getattr(campaign, "client_id", None)
    if not client_id:
        raise ClientInstagramError(
            "Campaign is not linked to a client. Cannot resolve Instagram credentials."
        )

    account = (
        db.query(ClientInstagramAccount)
        .filter(
            ClientInstagramAccount.client_id == client_id,
            ClientInstagramAccount.is_active == True,
        )
        .order_by(ClientInstagramAccount.id.desc())
        .first()
    )

    if not account:
        raise ClientInstagramError("No Instagram account connected for this client")

    if _is_token_expired(account.token_expires_at):
        raise ClientInstagramError(
            "Instagram connection expired for this client. Please reconnect Instagram."
        )

    if not account.access_token:
        raise ClientInstagramError(
            "Instagram access token is missing for this client"
        )

    if not account.instagram_account_id:
        raise ClientInstagramError(
            "Instagram account ID is missing for this client"
        )

    if not account.graph_base_url:
        raise ClientInstagramError(
            "Instagram graph base URL is missing for this client"
        )

    return {
        "graph_base_url": account.graph_base_url,
        "access_token": account.access_token,
        "instagram_account_id": account.instagram_account_id,
        "client_id": client_id,
    }
