import os
import tempfile
import uuid

import requests

from app.config import settings
from app.integrations.s3 import upload_file_to_s3


class AssetStorageError(Exception):
    """Raised when downloading or storing generated assets fails."""


def download_video_and_store(content_idea_id: int, source_video_url: str) -> dict:
    """
    Download a generated video from the provider and upload it to S3.
    Returns normalized S3 metadata.
    """
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp_file:
        temp_path = tmp_file.name

    try:
        response = requests.get(source_video_url, timeout=120)
        response.raise_for_status()

        with open(temp_path, "wb") as file_handle:
            file_handle.write(response.content)

        object_key = (
            f"{settings.S3_VIDEO_PREFIX}"
            f"content-idea-{content_idea_id}/"
            f"{uuid.uuid4()}.mp4"
        )

        return upload_file_to_s3(
            file_path=temp_path,
            object_key=object_key,
            content_type="video/mp4",
        )

    except requests.RequestException as exc:
        raise AssetStorageError(
            f"Failed to download provider video from {source_video_url}"
        ) from exc

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
