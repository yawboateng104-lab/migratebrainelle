from app.integrations.openai_client import client
from app.config import settings


class ExternalAnalyticsError(Exception):
    pass


def build_external_client_snapshot(payload: dict) -> dict:
    business_name = payload.get("business_name") or "Unknown Business"
    business_description = payload.get("business_description") or ""
    website_url = payload.get("website_url") or ""
    industry = payload.get("industry") or ""
    target_audience = payload.get("target_audience") or ""
    instagram_handle = payload.get("instagram_handle") or ""

    prompt = f"""
You are an external market research and onboarding strategist for an AI content SaaS.

Your task:
Create a helpful onboarding intelligence snapshot for a client.

Client info:
- Business name: {business_name}
- Business description: {business_description}
- Website URL: {website_url}
- Industry: {industry}
- Target audience: {target_audience}
- Instagram handle: {instagram_handle}

Return a JSON object with:
- onboarding_summary
- content_pillars (array of 3 strings)
- hook_ideas (array of 5 strings)
- tone_recommendation
- visual_recommendation
- music_vibe_suggestion
- posting_opportunities (array of 3 strings)

Requirements:
- Make it practical for Instagram short-form video content
- Make it feel specific and client-facing
- Do not be generic
- Keep it concise but valuable
"""

    try:
        response = client.responses.create(
            model=settings.OPENAI_REASONING_MODEL,
            input=prompt,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "external_client_snapshot",
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "onboarding_summary": {"type": "string"},
                            "content_pillars": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "hook_ideas": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "tone_recommendation": {"type": "string"},
                            "visual_recommendation": {"type": "string"},
                            "music_vibe_suggestion": {"type": "string"},
                            "posting_opportunities": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                        "required": [
                            "onboarding_summary",
                            "content_pillars",
                            "hook_ideas",
                            "tone_recommendation",
                            "visual_recommendation",
                            "music_vibe_suggestion",
                            "posting_opportunities",
                        ],
                    },
                    "strict": True,
                }
            },
        )
        import json
        return json.loads(response.output_text)
    except Exception as exc:
        raise ExternalAnalyticsError(f"Failed to build client snapshot: {exc}") from exc
