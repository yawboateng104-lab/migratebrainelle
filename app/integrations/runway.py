import time
from typing import Any

import requests

from app.config import settings


DEFAULT_RUNWAY_PROMPT = """
Subject: Confident female CEO

Action: Subject standing confidently, natural movement, subtle expressions

Environment Transformation:
Completely replace the original background with a luxurious high-rise executive office with floor-to-ceiling glass windows overlooking a modern city skyline at sunset.
The original background must be fully removed and not visible.

Lighting:
Match subject lighting to warm golden hour sunlight from the windows with cinematic shadows and highlights.

Integration:
Blend subject seamlessly into the new environment with correct perspective, reflections, and depth.

Style:
Ultra-realistic, photorealistic, 4K, shallow depth of field, HDR, luxury corporate aesthetic

Constraints:
Preserve facial identity, no distortion, maintain natural skin tone
Scene: Luxurious high-rise executive office with floor-to-ceiling glass windows overlooking a modern city skyline at sunset

Camera: Slow cinematic dolly-in shot

Motion: Subtle hair and clothing movement from ambient airflow, natural blinking, micro facial expressions

Background: City lights gradually turning on with realistic reflections on glass

Mood: Inspirational, powerful, aspirational leadership energy
Lens: 85mm cinematic lens
""".strip()


class RunwayError(Exception):
    """Raised when a Runway API call fails or returns an invalid response."""


def _get_auth_headers() -> dict[str, str]:
    if not settings.RUNWAY_API_KEY:
        raise RunwayError("Missing Runway API key")

    return {
        "Authorization": f"Bearer {settings.RUNWAY_API_KEY}",
        "Content-Type": "application/json",
        "X-Runway-Version": settings.RUNWAY_API_VERSION,
    }


def generate_image_to_video(
    image_url: str,
    prompt_text: str,
    duration_seconds: int = 5,
    ratio: str = "720:1280",
    model: str | None = None,
) -> dict[str, Any]:
    """
    Submit an image-to-video generation request to Runway.
    Returns the initial task payload.
    """
    if duration_seconds < 2 or duration_seconds > 10:
        raise RunwayError("Runway image-to-video duration must be between 2 and 10 seconds")

    url = f"{settings.RUNWAY_BASE_URL}/v1/image_to_video"

    resolved_prompt_text = (
        prompt_text.strip()
        if prompt_text and prompt_text.strip()
        else DEFAULT_RUNWAY_PROMPT
    )

    payload = {
        "model": model or settings.RUNWAY_MODEL,
        "promptImage": image_url,
        "promptText": resolved_prompt_text,
        "ratio": ratio,
        "duration": duration_seconds,
        "seed": 42,
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=_get_auth_headers(),
            timeout=120,
        )
    except requests.RequestException as exc:
        raise RunwayError(f"Runway image-to-video request failed: {exc}") from exc

    if response.status_code >= 400:
        raise RunwayError(
            f"Runway image-to-video request failed: {response.status_code} {response.text}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise RunwayError(f"Runway returned non-JSON response: {response.text}") from exc

    if "id" not in data:
        raise RunwayError(f"Unexpected Runway response: {data}")

    return data


def get_task_status(task_id: str) -> dict[str, Any]:
    """
    Fetch the latest Runway task state.
    """
    url = f"{settings.RUNWAY_BASE_URL}/v1/tasks/{task_id}"

    try:
        response = requests.get(
            url,
            headers=_get_auth_headers(),
            timeout=60,
        )
    except requests.RequestException as exc:
        raise RunwayError(f"Runway task status check failed: {exc}") from exc

    if response.status_code >= 400:
        raise RunwayError(
            f"Runway task status check failed: {response.status_code} {response.text}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise RunwayError(f"Runway task status returned non-JSON response: {response.text}") from exc

    if "status" not in data:
        raise RunwayError(f"Unexpected Runway task response: {data}")

    return data


def wait_for_video_completion(
    task_id: str,
    max_attempts: int = 90,
    sleep_seconds: int = 10,
) -> dict[str, Any]:
    """
    Poll Runway until the job completes, fails, or times out.
    Returns the final completed task response.
    """
    terminal_success = {"SUCCEEDED"}
    terminal_failure = {"FAILED", "CANCELLED"}
    last_data: dict[str, Any] | None = None
    transient_errors = 0
    max_transient_errors = 5

    for attempt in range(max_attempts):
        try:
            data = get_task_status(task_id=task_id)
            last_data = data
            transient_errors = 0
        except RunwayError as exc:
            transient_errors += 1
            if transient_errors > max_transient_errors:
                raise RunwayError(
                    f"Runway polling failed repeatedly for task {task_id}: {exc}"
                ) from exc

            time.sleep(sleep_seconds)
            continue

        status = str(data.get("status", "")).upper()

        print(
            f"[RUNWAY STATUS] task_id={task_id} "
            f"attempt={attempt + 1}/{max_attempts} status={status}"
        )

        if status in terminal_success:
            output = data.get("output") or []
            if not output:
                raise RunwayError(f"Runway task succeeded but no output found: {data}")
            return data

        if status in terminal_failure:
            error_message = data.get("error") or data.get("failureReason") or data
            raise RunwayError(f"Runway task failed: {error_message}")

        time.sleep(sleep_seconds)

    raise RunwayError(
        "Timed out waiting for Runway video completion "
        f"(task_id={task_id}, attempts={max_attempts}, sleep_seconds={sleep_seconds}, "
        f"last_status={last_data.get('status') if last_data else 'unknown'})"
    )
