import time
from typing import Any

import requests

from app.config import settings


class HiggsfieldError(Exception):
    """Raised when a Higgsfield API call fails or returns an invalid response."""


def _get_auth_headers() -> dict[str, str]:
    if not settings.HIGGSFIELD_API_KEY or not settings.HIGGSFIELD_API_SECRET:
        raise HiggsfieldError("Missing Higgsfield credentials")

    return {
        "Authorization": f"Key {settings.HIGGSFIELD_API_KEY}:{settings.HIGGSFIELD_API_SECRET}",
        "Content-Type": "application/json",
    }


def generate_image_to_video(image_url: str, prompt_text: str) -> dict[str, Any]:
    """
    Submit an image-to-video generation request to Higgsfield.
    Returns the initial provider response, typically with queued status and status_url.
    """
    url = f"{settings.HIGGSFIELD_BASE_URL}/kling-video/v2.1/pro/image-to-video"

    payload = {
        "image_url": image_url,
        "prompt": prompt_text,
    }

    response = requests.post(
        url,
        json=payload,
        headers=_get_auth_headers(),
        timeout=300,
    )

    if response.status_code >= 400:
        raise HiggsfieldError(
            f"Higgsfield image-to-video request failed: "
            f"{response.status_code} {response.text}"
        )

    data = response.json()

    if "status" not in data:
        raise HiggsfieldError(f"Unexpected Higgsfield response: {data}")

    return data


def get_video_status(status_url: str) -> dict[str, Any]:
    """
    Poll a Higgsfield status endpoint and return the latest job state.
    """
    response = requests.get(
        status_url,
        headers=_get_auth_headers(),
        timeout=120,
    )

    if response.status_code >= 400:
        raise HiggsfieldError(
            f"Higgsfield status check failed: {response.status_code} {response.text}"
        )

    data = response.json()

    if "status" not in data:
        raise HiggsfieldError(f"Unexpected Higgsfield status response: {data}")

    return data


def wait_for_video_completion(
    status_url: str,
    max_attempts: int = 30,
    sleep_seconds: int = 10,
) -> dict[str, Any]:
    """
    Poll Higgsfield until the job completes, fails, or times out.
    Returns the final completed response.
    """
    for _ in range(max_attempts):
        data = get_video_status(status_url=status_url)
        status = data.get("status")

        if status == "completed":
            return data

        if status in {"failed", "cancelled", "canceled"}:
            raise HiggsfieldError(f"Higgsfield job failed: {data}")

        time.sleep(sleep_seconds)

    raise HiggsfieldError("Timed out waiting for Higgsfield video completion")
