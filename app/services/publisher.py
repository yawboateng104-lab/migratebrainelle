from app.integrations.instagram import (
    InstagramError,
    create_image_container,
    create_video_container,
    publish_media,
)


class PublisherError(Exception):
    pass


def publish_to_instagram(
    asset_url: str,
    caption: str,
    media_type: str,
    graph_base_url: str | None = None,
    access_token: str | None = None,
    instagram_account_id: str | None = None,
) -> dict:
    normalized_media_type = media_type.lower().strip()

    if not asset_url.startswith("https://"):
        raise PublisherError("Asset URL must be a public HTTPS URL")

    try:
        if normalized_media_type == "image":
            creation_id = create_image_container(
                image_url=asset_url,
                caption=caption,
                graph_base_url=graph_base_url,
                access_token=access_token,
                instagram_account_id=instagram_account_id,
            )
        elif normalized_media_type == "video":
            creation_id = create_video_container(
                video_url=asset_url,
                caption=caption,
                graph_base_url=graph_base_url,
                access_token=access_token,
                instagram_account_id=instagram_account_id,
            )
        else:
            raise PublisherError(
                f"Unsupported media_type '{media_type}'. Use 'image' or 'video'."
            )

        post_id = publish_media(
            creation_id=creation_id,
            graph_base_url=graph_base_url,
            access_token=access_token,
            instagram_account_id=instagram_account_id,
        )

        return {
            "platform": "instagram",
            "platform_post_id": post_id,
            "publish_status": "published",
            "caption_used": caption,
            "asset_url": asset_url,
            "media_type": normalized_media_type,
        }

    except InstagramError as exc:
        raise PublisherError(f"Instagram publish failed: {exc}") from exc
