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


def _parse_json_response(response: requests.Response, context: str) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as exc:
        raise HiggsfieldError(f"{context}: non-JSON response returned from Higgsfield") from exc

    if not isinstance(data, dict):
        raise HiggsfieldError(f"{context}: unexpected response shape: {data}")

    if "status" not in data:
        raise HiggsfieldError(f"{context}: unexpected Higgsfield response: {data}")

    return data


def _normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_quality(value: str | None, default: str = "medium") -> str:
    allowed = {"medium", "high"}
    normalized = _normalize_text(value).lower()
    if normalized in allowed:
        return normalized
    return default


def _normalize_size(value: str | None, default: str = "1152*2048") -> str:
    normalized = _normalize_text(value)
    return normalized or default


def _normalize_strength(value: float | int | None, default: float = 0.30) -> float:
    if value is None:
        return default

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return default

    if numeric_value < 0:
        return 0.0
    if numeric_value > 1:
        return 1.0
    return numeric_value


def generate_image_to_video(image_url: str, prompt_text: str) -> dict[str, Any]:
    image_url = _normalize_text(image_url)
    prompt_text = _normalize_text(prompt_text)

    if not image_url:
        raise HiggsfieldError("image_url is required for Higgsfield image_to_video")
    if not prompt_text:
        raise HiggsfieldError("prompt_text is required for Higgsfield image_to_video")

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

    return _parse_json_response(response, "Higgsfield image-to-video request failed")


def generate_text_to_image(
    prompt_text: str,
    *,
    size: str = "1152*2048",
    quality: str = "medium",
    style: str | None = None,
) -> dict[str, Any]:
    prompt_text = _normalize_text(prompt_text)

    if not prompt_text:
        raise HiggsfieldError("prompt_text is required for Higgsfield text_to_image")

    url = f"{settings.HIGGSFIELD_BASE_URL}/higgsfield-ai/soul/standard"

    payload: dict[str, Any] = {
        "prompt": prompt_text,
        "size": _normalize_size(size),
        "quality": _normalize_quality(quality),
    }

    normalized_style = _normalize_text(style)
    if normalized_style:
        payload["style"] = normalized_style

    response = requests.post(
        url,
        json=payload,
        headers=_get_auth_headers(),
        timeout=300,
    )

    if response.status_code >= 400:
        raise HiggsfieldError(
            f"Higgsfield text-to-image request failed: "
            f"{response.status_code} {response.text}"
        )

    return _parse_json_response(response, "Higgsfield text-to-image request failed")


def generate_image_with_reference(
    image_url: str,
    prompt_text: str,
    *,
    size: str = "1152*2048",
    strength: float = 0.30,
    quality: str = "medium",
    style: str | None = None,
    custom_reference_id: str | None = None,
) -> dict[str, Any]:
    """
    Reference-driven Soul generation.

    Your backend error shows Soul mode must be one of:
    - standard
    - reference
    - character

    So for uploaded-face guidance we use /soul/reference.
    """
    image_url = _normalize_text(image_url)
    prompt_text = _normalize_text(prompt_text)

    if not image_url:
        raise HiggsfieldError("image_url is required for Higgsfield image_with_reference")
    if not prompt_text:
        raise HiggsfieldError("prompt_text is required for Higgsfield image_with_reference")

    url = f"{settings.HIGGSFIELD_BASE_URL}/higgsfield-ai/soul/reference"

    payload: dict[str, Any] = {
        "prompt": prompt_text,
        "image_url": image_url,
        "size": _normalize_size(size),
        "quality": _normalize_quality(quality),
        "reference_strength": _normalize_strength(strength),
    }

    normalized_style = _normalize_text(style)
    if normalized_style:
        payload["style"] = normalized_style

    normalized_reference_id = _normalize_text(custom_reference_id)
    if normalized_reference_id:
        payload["custom_reference_id"] = normalized_reference_id

    response = requests.post(
        url,
        json=payload,
        headers=_get_auth_headers(),
        timeout=300,
    )

    if response.status_code >= 400:
        raise HiggsfieldError(
            f"Higgsfield image-with-reference request failed: "
            f"{response.status_code} {response.text}"
        )

    return _parse_json_response(response, "Higgsfield image-with-reference request failed")


def get_job_status(status_url: str) -> dict[str, Any]:
    status_url = _normalize_text(status_url)
    if not status_url:
        raise HiggsfieldError("status_url is required")

    response = requests.get(
        status_url,
        headers=_get_auth_headers(),
        timeout=120,
    )

    if response.status_code >= 400:
        raise HiggsfieldError(
            f"Higgsfield status check failed: {response.status_code} {response.text}"
        )

    return _parse_json_response(response, "Higgsfield status check failed")


def wait_for_video_completion(
    status_url: str,
    max_attempts: int = 30,
    sleep_seconds: int = 10,
) -> dict[str, Any]:
    for _ in range(max_attempts):
        data = get_job_status(status_url=status_url)
        status = str(data.get("status", "")).lower()

        if status in {"completed", "success", "succeeded"}:
            return data

        if status in {"failed", "cancelled", "canceled", "error"}:
            raise HiggsfieldError(f"Higgsfield video job failed: {data}")

        time.sleep(sleep_seconds)

    raise HiggsfieldError("Timed out waiting for Higgsfield video completion")


def wait_for_image_completion(
    status_url: str,
    max_attempts: int = 30,
    sleep_seconds: int = 10,
) -> dict[str, Any]:
    for _ in range(max_attempts):
        data = get_job_status(status_url=status_url)
        status = str(data.get("status", "")).lower()

        if status in {"completed", "success", "succeeded"}:
            return data

        if status in {"failed", "cancelled", "canceled", "error"}:
            raise HiggsfieldError(f"Higgsfield image job failed: {data}")

        time.sleep(sleep_seconds)

    raise HiggsfieldError("Timed out waiting for Higgsfield image completion")
