from app.config import settings
from app.pg_tables import Campaign, ContentIdea, ClientInstagramAccount


class ClientInstagramError(Exception):
    pass


def get_instagram_credentials_for_content_idea(content_idea_id: int, db) -> dict:
    content_idea = db.get(ContentIdea, content_idea_id)
    if not content_idea:
        raise ClientInstagramError("Content idea not found")

    campaign = db.get(Campaign, content_idea.campaign_id)
    if not campaign:
        raise ClientInstagramError("Campaign not found")

    client_id = getattr(campaign, "client_id", None)

    if client_id:
        account = (
            db.query(ClientInstagramAccount)
            .filter(
                ClientInstagramAccount.client_id == client_id,
                ClientInstagramAccount.is_active == True,
            )
            .first()
        )

        if account:
            return {
                "graph_base_url": account.graph_base_url,
                "access_token": account.access_token,
                "instagram_account_id": account.instagram_account_id,
                "client_id": client_id,
            }

    if settings.INSTAGRAM_ACCESS_TOKEN and settings.INSTAGRAM_ACCOUNT_ID:
        return {
            "graph_base_url": settings.INSTAGRAM_GRAPH_BASE_URL,
            "access_token": settings.INSTAGRAM_ACCESS_TOKEN,
            "instagram_account_id": settings.INSTAGRAM_ACCOUNT_ID,
            "client_id": client_id,
        }

    raise ClientInstagramError("No Instagram credentials configured for this content idea")
