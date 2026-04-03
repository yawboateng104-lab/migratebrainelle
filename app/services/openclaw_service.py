import json
import re
from typing import Any

import requests

from app.config import settings


class OpenClawError(Exception):
    """Raised when an OpenClaw request or response fails."""


def _extract_json_object(text: str) -> dict[str, Any]:
    """
    Extract a JSON object from a model response.
    Supports:
    1. direct JSON
    2. fenced ```json blocks
    3. first JSON object found in text
    """
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced_match:
        try:
            return json.loads(fenced_match.group(1))
        except json.JSONDecodeError as exc:
            raise OpenClawError(
                f"Failed to parse fenced JSON from OpenClaw response: {text}"
            ) from exc

    object_match = re.search(r"(\{.*\})", text, re.DOTALL)
    if object_match:
        try:
            return json.loads(object_match.group(1))
        except json.JSONDecodeError as exc:
            raise OpenClawError(
                f"Failed to parse embedded JSON from OpenClaw response: {text}"
            ) from exc

    raise OpenClawError(f"Could not extract JSON from OpenClaw response: {text}")


def _call_openclaw(prompt: str, system_prompt: str | None = None) -> str:
    """
    Call OpenClaw chat completions endpoint and return raw text content.
    """
    if not settings.OPENCLAW_BASE_URL:
        raise OpenClawError("Missing OPENCLAW_BASE_URL")
    if not settings.OPENCLAW_MODEL:
        raise OpenClawError("Missing OPENCLAW_MODEL")
    if not settings.OPENCLAW_TOKEN:
        raise OpenClawError("Missing OPENCLAW_TOKEN")

    url = f"{settings.OPENCLAW_BASE_URL.rstrip('/')}/v1/chat/completions"

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": settings.OPENCLAW_MODEL,
        "messages": messages,
        "stream": False,
        "temperature": 0.2,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.OPENCLAW_TOKEN}",
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=120,
        )
    except requests.RequestException as exc:
        raise OpenClawError("Failed to connect to OpenClaw") from exc

    if response.status_code != 200:
        raise OpenClawError(
            f"OpenClaw returned {response.status_code}: {response.text}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise OpenClawError(
            f"OpenClaw returned non-JSON response: {response.text}"
        ) from exc

    try:
        content = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise OpenClawError(f"Unexpected OpenClaw response shape: {data}") from exc

    if "rate limit" in content.lower():
        raise OpenClawError(content)

    return content


def interpret_user_command(text: str) -> dict[str, Any]:
    """
    Interpret a Telegram/user message into a structured action.

    Supported actions:
    - runway
    - higgsfield
    - approve
    - reject
    - insights

    If the action is approve/reject, include asset_id when possible.
    """
    system_prompt = """
You are an AI router for a marketing automation agent.

Your job is to convert a user message into a single structured JSON action.

Return JSON only.
Do not wrap output in markdown fences.
Do not add explanation before or after the JSON.

Supported actions:
- runway
- higgsfield
- approve
- reject
- insights
- unknown

Rules:
- If the user wants a cinematic or premium generated video, prefer "runway"
- If the user explicitly says higgsfield, use "higgsfield"
- If the user asks to approve a draft/post/video, use "approve"
- If the user asks to reject a draft/post/video, use "reject"
- If the user asks for analytics, summary, performance, or insights, use "insights"
- If you cannot confidently map the request, use "unknown"

If the user includes an asset id, extract it as an integer.

Return JSON with this exact schema:
{
  "action": "runway|higgsfield|approve|reject|insights|unknown",
  "asset_id": 123 or null
}
""".strip()

    prompt = f"""
User message:
{text}
""".strip()

    raw = _call_openclaw(prompt=prompt, system_prompt=system_prompt)
    parsed = _extract_json_object(raw)

    action = parsed.get("action")
    asset_id = parsed.get("asset_id")

    allowed_actions = {
        "runway",
        "higgsfield",
        "approve",
        "reject",
        "insights",
        "unknown",
    }

    if action not in allowed_actions:
        raise OpenClawError(f"Unsupported action returned by OpenClaw: {parsed}")

    if asset_id is not None:
        try:
            asset_id = int(asset_id)
        except (TypeError, ValueError) as exc:
            raise OpenClawError(f"Invalid asset_id returned by OpenClaw: {parsed}") from exc

    return {
        "action": action,
        "asset_id": asset_id,
    }


def generate_script_with_openclaw(content_idea: Any, campaign: Any) -> dict[str, Any]:
    """
    Generate a high-quality short-form script package.
    """
    system_prompt = """
You are an elite short-form content strategist and social video copywriter.

Your job is to create highly engaging 15-30 second Instagram Reel scripts
that feel natural, human, cinematic, and creator-native.

Return JSON only.
Do not wrap output in markdown fences.
Do not add explanation before or after the JSON.
Do not use placeholder phrasing.
Do not write robotic marketing copy.
Do not repeat the user's instructions in the output.

Your writing style:
- sharp, punchy, emotionally clear
- natural founder/creator tone
- social-first, not corporate
- hook must hit in the first 1-2 seconds
- copy should sound like something a real creator would actually say
- avoid generic filler like "provide actionable tips" or "learn more today"

The caption should:
- feel social and human
- not sound over-produced
- support the video without repeating it word-for-word

The script should:
- be concise enough for a 15-30 second reel
- have strong opening momentum
- build toward a payoff
- end with a clean CTA

Return valid JSON only.
""".strip()

    prompt = f"""
Return JSON with this exact schema:
{{
  "hook": "string",
  "script_text": "string",
  "caption": "string",
  "hashtags": "string",
  "voiceover_text": "string"
}}

Campaign:
- app_name: {campaign.app_name}
- app_description: {campaign.app_description}
- audience: {campaign.audience}
- tone: {campaign.tone}
- cta: {campaign.cta}
- instagram_handle: {campaign.instagram_handle}

Content idea:
- pillar: {content_idea.pillar}
- title: {content_idea.title}
- hook seed: {content_idea.hook}
- angle: {content_idea.angle}
- format: {content_idea.format}

Creative requirements:
- optimize for a 15-30 second Instagram Reel
- hook should land in the first sentence
- script should feel cinematic, punchy, and social-native
- script should sound like a creator/founder speaking on camera
- no placeholder language
- no bullet points inside script_text
- voiceover_text should sound natural when spoken out loud
- caption should feel compelling but concise
- hashtags should be a single string

Content structure:
- first 1-2 seconds: hook
- next section: fast setup or insight
- next section: payoff, insight, or emotional turn
- ending: subtle CTA aligned to the campaign CTA

Make it feel premium, persuasive, and real.
""".strip()

    raw = _call_openclaw(prompt=prompt, system_prompt=system_prompt)
    return _extract_json_object(raw)


def generate_video_prompt_with_openclaw(
    content_idea: Any,
    campaign: Any,
    script: Any,
) -> dict[str, Any]:
    """
    Generate a cinematic short-form video prompt package.
    """
    system_prompt = """
You are an elite AI video prompt director for cinematic short-form social content.

Your job is to convert marketing ideas into visually rich, 15-30 second
vertical Instagram Reel concepts that feel premium, cinematic, emotionally engaging,
and realistic enough to perform well in short-form feeds.

Return JSON only.
Do not wrap output in markdown fences.
Do not add explanation before or after the JSON.
Do not produce vague generic prompts.
Do not output placeholders.

The prompt should be optimized for:
- vertical 9:16 framing
- 15-30 second duration
- strong opening frame
- smooth visual pacing
- cinematic realism
- creator/founder-led storytelling when appropriate
- premium social ad feel

Use visual language like:
- soft dramatic lighting
- shallow depth of field
- subtle dolly-in
- handheld realism
- premium commercial aesthetic
- emotionally engaging opening frame
- fast but smooth edit pacing

The output must be detailed enough that a video generator can create
a compelling cinematic reel, not just a generic social clip.
""".strip()

    prompt = f"""
Return JSON with this exact schema:
{{
  "prompt_text": "string",
  "shot_list": "string",
  "visual_style": "string",
  "camera_notes": "string",
  "duration_seconds": 20,
  "opening_frame_description": "string",
  "mood": "string",
  "editing_pace": "string",
  "cta_overlay_text": "string"
}}

Campaign:
- app_name: {campaign.app_name}
- app_description: {campaign.app_description}
- audience: {campaign.audience}
- tone: {campaign.tone}
- cta: {campaign.cta}

Content idea:
- pillar: {content_idea.pillar}
- title: {content_idea.title}
- hook: {content_idea.hook}
- angle: {content_idea.angle}
- format: {content_idea.format}

Script:
- hook: {script.hook}
- script_text: {script.script_text}
- caption: {script.caption}
- voiceover_text: {script.voiceover_text}

Creative direction:
- make this a 15-30 second cinematic Instagram Reel
- build for vertical 9:16
- strong opening frame in the first 1-2 seconds
- premium, polished social-ad quality
- realistic human presence when relevant
- visual pacing should be smooth, emotional, and intentional
- avoid generic “make a reel about” phrasing
- write as a cinematic scene direction, not just a topic summary

Shot strategy:
- opening shot should immediately stop the scroll
- middle should visually reinforce the main insight or emotional turn
- ending should support CTA or brand recall
- shots should feel achievable, not random
- if founder-led, keep it intimate, direct-to-camera, and premium

Prompt quality requirements:
- prompt_text should be rich and vivid
- shot_list should be concise but visually useful
- visual_style should describe the aesthetic
- camera_notes should describe movement, framing, and lens feel
- duration_seconds should usually be between 15 and 30
- opening_frame_description should clearly describe the first frame
- mood should describe emotional tone
- editing_pace should describe rhythm of the reel
- cta_overlay_text should be short and on-brand

Return only valid JSON.
""".strip()

    raw = _call_openclaw(prompt=prompt, system_prompt=system_prompt)
    return _extract_json_object(raw)
