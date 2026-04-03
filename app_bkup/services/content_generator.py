from typing import Any

from app.services.openclaw_service import (
    generate_script_with_openclaw,
    generate_video_prompt_with_openclaw,
)


def generate_script_from_idea(content_idea: Any, campaign: Any) -> dict:
    """
    Generate a short-form script package from a content idea and campaign.
    """
    return generate_script_with_openclaw(
        content_idea=content_idea,
        campaign=campaign,
    )


def generate_video_prompt_from_script(
    content_idea: Any,
    campaign: Any,
    script: Any,
) -> dict:
    """
    Generate a structured video prompt package from a content idea, campaign, and script.
    """
    return generate_video_prompt_with_openclaw(
        content_idea=content_idea,
        campaign=campaign,
        script=script,
    )
