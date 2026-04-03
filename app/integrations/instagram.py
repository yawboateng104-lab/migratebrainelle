import time

import requests

from app.config import settings


class InstagramError(Exception):
    pass


def _require_instagram_config(
    graph_base_url: str | None,
    access_token: str | None,
    instagram_account_id: str | None,
) -> None:
    if not graph_base_url:
        raise InstagramError("Missing INSTAGRAM_GRAPH_BASE_URL")
    if not access_token:
        raise InstagramError("Missing Instagram access token from DB")
    if not instagram_account_id:
        raise InstagramError("Missing Instagram account ID from DB")


def _debug_log(
    prefix: str,
    graph_base_url: str | None,
    access_token: str | None,
    instagram_account_id: str | None,
) -> None:
    token = access_token or ""
    print(f"\n[IG DEBUG] {prefix}")
    print(f"[IG DEBUG] GRAPH_BASE: {graph_base_url}")
    print(f"[IG DEBUG] ACCOUNT_ID: {instagram_account_id}")
    print(f"[IG DEBUG] TOKEN_PREFIX: {token[:20]}")
    print(f"[IG DEBUG] TOKEN_SUFFIX: {token[-8:] if token else ''}")


def create_image_container(
    image_url: str,
    caption: str,
    graph_base_url: str | None = None,
    access_token: str | None = None,
    instagram_account_id: str | None = None,
) -> str:
    graph_base_url = graph_base_url or settings.INSTAGRAM_GRAPH_BASE_URL

    _require_instagram_config(graph_base_url, access_token, instagram_account_id)
    _debug_log("CREATE IMAGE CONTAINER", graph_base_url, access_token, instagram_account_id)

    url = f"{graph_base_url}/{instagram_account_id}/media"

    payload = {
        "image_url": image_url,
        "caption": caption,
        "access_token": access_token,
    }

    response = requests.post(url, data=payload, timeout=120)
    print("[IG RESPONSE]", response.status_code, response.text)

    if response.status_code != 200:
        raise InstagramError(
            f"Failed to create image container: {response.status_code} {response.text}"
        )

    data = response.json()
    creation_id = data.get("id")
    if not creation_id:
        raise InstagramError(f"Invalid image container response: {data}")

    return creation_id


def create_video_container(
    video_url: str,
    caption: str,
    graph_base_url: str | None = None,
    access_token: str | None = None,
    instagram_account_id: str | None = None,
) -> str:
    graph_base_url = graph_base_url or settings.INSTAGRAM_GRAPH_BASE_URL

    _require_instagram_config(graph_base_url, access_token, instagram_account_id)
    _debug_log("CREATE VIDEO CONTAINER", graph_base_url, access_token, instagram_account_id)
    print("[IG VIDEO URL]", video_url)

    url = f"{graph_base_url}/{instagram_account_id}/media"

    payload = {
        "video_url": video_url,
        "caption": caption,
        "media_type": "REELS",
        "access_token": access_token,
    }

    response = requests.post(url, data=payload, timeout=120)
    print("[IG RESPONSE]", response.status_code, response.text)

    if response.status_code != 200:
        raise InstagramError(
            f"Failed to create video container: {response.status_code} {response.text}"
        )

    data = response.json()
    creation_id = data.get("id")
    if not creation_id:
        raise InstagramError(f"Invalid video container response: {data}")

    return creation_id


def wait_for_media_ready(
    creation_id: str,
    max_attempts: int = 15,
    sleep_seconds: int = 5,
    graph_base_url: str | None = None,
    access_token: str | None = None,
    instagram_account_id: str | None = None,
) -> None:
    graph_base_url = graph_base_url or settings.INSTAGRAM_GRAPH_BASE_URL

    _require_instagram_config(graph_base_url, access_token, instagram_account_id)

    url = f"{graph_base_url}/{creation_id}"

    for attempt in range(max_attempts):
        response = requests.get(
            url,
            params={
                "fields": "status_code",
                "access_token": access_token,
            },
            timeout=60,
        )

        data = response.json()
        status_code = data.get("status_code")
        print(f"[IG STATUS] attempt={attempt} status={status_code}")

        if status_code == "FINISHED":
            return

        if status_code == "ERROR":
            raise InstagramError(f"Media processing failed: {data}")

        time.sleep(sleep_seconds)

    raise InstagramError("Timed out waiting for media to be ready")


def publish_media(
    creation_id: str,
    graph_base_url: str | None = None,
    access_token: str | None = None,
    instagram_account_id: str | None = None,
) -> str:
    graph_base_url = graph_base_url or settings.INSTAGRAM_GRAPH_BASE_URL

    _require_instagram_config(graph_base_url, access_token, instagram_account_id)
    _debug_log("PUBLISH MEDIA", graph_base_url, access_token, instagram_account_id)

    wait_for_media_ready(
        creation_id=creation_id,
        graph_base_url=graph_base_url,
        access_token=access_token,
        instagram_account_id=instagram_account_id,
    )

    url = f"{graph_base_url}/{instagram_account_id}/media_publish"

    payload = {
        "creation_id": creation_id,
        "access_token": access_token,
    }

    response = requests.post(url, data=payload, timeout=120)
    print("[IG PUBLISH RESPONSE]", response.status_code, response.text)

    if response.status_code != 200:
        raise InstagramError(
            f"Failed to publish media: {response.status_code} {response.text}"
        )

    data = response.json()
    post_id = data.get("id")
    if not post_id:
        raise InstagramError(f"Invalid publish response: {data}")

    return post_id
