from app.pg_tables import Campaign, Client, ContentIdea
from app.services.telegram_media_service import get_latest_uploaded_source_image_s3_key_for_chat


class TelegramContextError(Exception):
    pass


def get_generation_context_for_chat(chat_id: int | str, db) -> dict:
    client = (
        db.query(Client)
        .filter(Client.telegram_chat_id == str(chat_id))
        .first()
    )
    if not client:
        raise TelegramContextError(
            "No client is linked to this Telegram chat yet."
        )

    campaign = (
        db.query(Campaign)
        .filter(Campaign.client_id == client.id)
        .order_by(Campaign.id.desc())
        .first()
    )
    if not campaign:
        raise TelegramContextError(
            "No campaign found for this client."
        )

    content_idea = (
        db.query(ContentIdea)
        .filter(ContentIdea.campaign_id == campaign.id)
        .order_by(ContentIdea.id.desc())
        .first()
    )
    if not content_idea:
        raise TelegramContextError(
            "No content idea found for this client’s campaign."
        )

    uploaded_source_image_s3_key = get_latest_uploaded_source_image_s3_key_for_chat(
        db=db,
        chat_id=chat_id,
    )

    default_source_image_s3_key = getattr(campaign, "default_source_image_s3_key", None)
    source_image_s3_key = uploaded_source_image_s3_key or default_source_image_s3_key
    logo_s3_key = getattr(campaign, "logo_s3_key", None)

    return {
        "client_id": client.id,
        "campaign_id": campaign.id,
        "content_idea_id": content_idea.id,
        "source_image_s3_key": source_image_s3_key,
        "uploaded_source_image_s3_key": uploaded_source_image_s3_key,
        "default_source_image_s3_key": default_source_image_s3_key,
        "logo_s3_key": logo_s3_key,
    }


def link_telegram_chat_to_client(chat_id: int | str, client_id: int, db) -> dict:
    """
    Strict tenant-safe linking.

    Security behavior:
    - A Telegram chat can only link to a client already assigned to that exact chat_id
    - If the client does not exist, or belongs to a different chat, return a generic error
    - This prevents one client from linking to another client's profile by guessing IDs
    """
    client = db.get(Client, client_id)

    if not client:
        raise TelegramContextError("Client is not available for this Telegram chat.")

    assigned_chat_id = (client.telegram_chat_id or "").strip()
    current_chat_id = str(chat_id).strip()

    if not assigned_chat_id:
        raise TelegramContextError("Client is not available for this Telegram chat.")

    if assigned_chat_id != current_chat_id:
        raise TelegramContextError("Client is not available for this Telegram chat.")

    existing_client_for_chat = (
        db.query(Client)
        .filter(Client.telegram_chat_id == current_chat_id)
        .first()
    )

    if not existing_client_for_chat:
        raise TelegramContextError("Client is not available for this Telegram chat.")

    if existing_client_for_chat.id != client.id:
        raise TelegramContextError("Client is not available for this Telegram chat.")

    return {
        "client_id": client.id,
        "telegram_chat_id": client.telegram_chat_id,
        "status": "linked",
    }
