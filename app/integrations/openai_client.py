import json

from openai import OpenAI

from app.config import settings


client = OpenAI(api_key=settings.OPENAI_API_KEY)


def generate_structured_creative_spec(payload: dict) -> dict:
    response = client.responses.create(
        model=settings.OPENAI_REASONING_MODEL,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a creative strategy and prompt orchestration engine for an AI Content Agent SaaS. "
                    "You must return only valid JSON matching the requested schema. "

                    "Your job is to synthesize multiple layers of structured input into a single high-quality, "
                    "provider-ready creative execution spec for social media content generation. "

                    "You may receive structured input containing: "
                    "creative_request, media_inputs, provider_context, prompt_template, client_prompt_profile, "
                    "runtime_overrides, feedback_signals, raw_input_json, and instructions. "

                    "You MUST intelligently merge all relevant layers of input into one final resolved output. "

                    "INPUT MERGE PRIORITY (highest to lowest): "
                    "1. runtime_overrides, especially edit_request and edit_notes. "
                    "2. creative_request fields such as hook, angle, tone, CTA, topic, description, "
                    "visual_style, scene_description, and extra_instructions. "
                    "3. client_prompt_profile, including brand_voice, style_rules, creative_guidelines, "
                    "cta_guidelines, and negative_prompt. "
                    "4. prompt_template, including system_prompt and user_prompt. "
                    "5. feedback_signals and analytics recommendations. "

                    "EDIT REVISION RULES: "
                    "If runtime_overrides.edit_request exists, treat the request as a revision of an existing creative. "
                    "Apply edit_notes and all requested changes such as hook, CTA, tone, visual style, environment, "
                    "lighting, camera style, motion intensity, music notes, and shot updates. "
                    "Edit instructions override previous creative direction. Do not ignore them. "

                    "TEMPLATE RULES: "
                    "If prompt_template.system_prompt exists, use it as creative guidance and structural context. "
                    "If prompt_template.user_prompt exists, use it as a strong base for the final prompt_text, "
                    "but adapt it dynamically using the creative_request, profile, analytics, and runtime overrides. "
                    "Do not copy a generic template blindly. Resolve it into a concrete, client-specific output. "

                    "PROFILE RULES: "
                    "client_prompt_profile defines brand voice, tone, stylistic constraints, CTA preferences, "
                    "and negative prompting guidance. Your output must align with that profile. "

                    "PROVIDER AND WORKFLOW RULES: "
                    "Respect provider_context when it is present. "
                    "Prefer image_to_video when a strong source image exists. "
                    "Use runway_cinematic for cinematic storytelling, stronger multi-shot narratives, or voiceover-led output. "
                    "Use heygen_avatar only for avatar-style content. "
                    "Do not choose avatar workflows unless the request clearly calls for it. "

                    "PROMPT QUALITY RULES: "
                    "prompt_text must be specific, cinematic, visual, and production-ready. "
                    "Avoid bland or generic descriptions. "
                    "Adapt the environment, lighting, camera movement, pacing, mood, and styling to the client's brand, "
                    "audience, offer, and platform. "
                    "When appropriate, maintain identity and environment continuity from source imagery. "

                    "SHOT RULES: "
                    "When useful, generate multiple shot_prompts to support storytelling and future multi-shot pipelines. "
                    "Shots should have logical progression, varied framing or movement, and coherent pacing. "

                    "CAPTION AND HASHTAG RULES: "
                    "caption_text should be platform-appropriate and aligned with the creative goal. "
                    "hashtags should be concise, relevant, and usable as a single string. "

                    "PROVIDER PAYLOAD RULES: "
                    "provider_payload_json must remain tightly structured and only use fields allowed by the schema. "
                    "Do not invent any fields outside the schema. "

                    "OUTPUT RULES: "
                    "Return only valid JSON. "
                    "Do not include markdown. "
                    "Do not include explanations. "
                    "All required fields must be present. "
                    "If a field is unknown or not needed, return null where allowed by schema."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload),
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "resolved_creative_spec",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "provider": {"type": "string"},
                        "workflow": {"type": "string"},
                        "generation_mode": {"type": "string"},
                        "prompt_text": {"type": "string"},
                        "negative_prompt": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "null"},
                            ]
                        },
                        "voiceover_script": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "null"},
                            ]
                        },
                        "caption_text": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "null"},
                            ]
                        },
                        "hashtags": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "null"},
                            ]
                        },
                        "provider_payload_json": {
                            "anyOf": [
                                {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "ratio": {
                                            "anyOf": [
                                                {"type": "string"},
                                                {"type": "null"},
                                            ]
                                        },
                                        "voice_id": {
                                            "anyOf": [
                                                {"type": "string"},
                                                {"type": "null"},
                                            ]
                                        },
                                        "visual_style_override": {
                                            "anyOf": [
                                                {"type": "string"},
                                                {"type": "null"},
                                            ]
                                        },
                                        "camera_style": {
                                            "anyOf": [
                                                {"type": "string"},
                                                {"type": "null"},
                                            ]
                                        },
                                        "motion_intensity": {
                                            "anyOf": [
                                                {"type": "string"},
                                                {"type": "null"},
                                            ]
                                        },
                                        "environment_style": {
                                            "anyOf": [
                                                {"type": "string"},
                                                {"type": "null"},
                                            ]
                                        },
                                        "lighting_style": {
                                            "anyOf": [
                                                {"type": "string"},
                                                {"type": "null"},
                                            ]
                                        },
                                        "preserve_environment": {
                                            "anyOf": [
                                                {"type": "boolean"},
                                                {"type": "null"},
                                            ]
                                        },
                                        "preserve_identity": {
                                            "anyOf": [
                                                {"type": "boolean"},
                                                {"type": "null"},
                                            ]
                                        },
                                        "use_source_image_strongly": {
                                            "anyOf": [
                                                {"type": "boolean"},
                                                {"type": "null"},
                                            ]
                                        },
                                        "shot_prompts": {
                                            "anyOf": [
                                                {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "additionalProperties": False,
                                                        "properties": {
                                                            "shot_number": {"type": "integer"},
                                                            "shot_name": {
                                                                "anyOf": [
                                                                    {"type": "string"},
                                                                    {"type": "null"},
                                                                ]
                                                            },
                                                            "prompt": {"type": "string"},
                                                            "duration_seconds": {
                                                                "anyOf": [
                                                                    {"type": "integer"},
                                                                    {"type": "null"},
                                                                ]
                                                            },
                                                            "camera_move": {
                                                                "anyOf": [
                                                                    {"type": "string"},
                                                                    {"type": "null"},
                                                                ]
                                                            },
                                                            "transition_style": {
                                                                "anyOf": [
                                                                    {"type": "string"},
                                                                    {"type": "null"},
                                                                ]
                                                            },
                                                        },
                                                        "required": [
                                                            "shot_number",
                                                            "shot_name",
                                                            "prompt",
                                                            "duration_seconds",
                                                            "camera_move",
                                                            "transition_style",
                                                        ],
                                                    },
                                                },
                                                {"type": "null"},
                                            ]
                                        },
                                        "platform_rendering_hints": {
                                            "anyOf": [
                                                {
                                                    "type": "object",
                                                    "additionalProperties": False,
                                                    "properties": {
                                                        "target_platform": {
                                                            "anyOf": [
                                                                {"type": "string"},
                                                                {"type": "null"},
                                                            ]
                                                        },
                                                        "target_aspect_ratio": {
                                                            "anyOf": [
                                                                {"type": "string"},
                                                                {"type": "null"},
                                                            ]
                                                        },
                                                        "optimize_for_short_form_hook": {
                                                            "anyOf": [
                                                                {"type": "boolean"},
                                                                {"type": "null"},
                                                            ]
                                                        },
                                                        "safe_text_overlay_regions": {
                                                            "anyOf": [
                                                                {"type": "boolean"},
                                                                {"type": "null"},
                                                            ]
                                                        },
                                                    },
                                                    "required": [
                                                        "target_platform",
                                                        "target_aspect_ratio",
                                                        "optimize_for_short_form_hook",
                                                        "safe_text_overlay_regions",
                                                    ],
                                                },
                                                {"type": "null"},
                                            ]
                                        },
                                    },
                                    "required": [
                                        "ratio",
                                        "voice_id",
                                        "visual_style_override",
                                        "camera_style",
                                        "motion_intensity",
                                        "environment_style",
                                        "lighting_style",
                                        "preserve_environment",
                                        "preserve_identity",
                                        "use_source_image_strongly",
                                        "shot_prompts",
                                        "platform_rendering_hints",
                                    ],
                                },
                                {"type": "null"},
                            ]
                        },
                        "resolution_notes": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "null"},
                            ]
                        },
                    },
                    "required": [
                        "provider",
                        "workflow",
                        "generation_mode",
                        "prompt_text",
                        "negative_prompt",
                        "voiceover_script",
                        "caption_text",
                        "hashtags",
                        "provider_payload_json",
                        "resolution_notes",
                    ],
                },
                "strict": True,
            }
        },
    )

    return json.loads(response.output_text)


def generate_campaign_bootstrap(payload: dict) -> dict:
    response = client.responses.create(
        model=settings.OPENAI_REASONING_MODEL,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a campaign planning strategist for an AI social media SaaS. "
                    "Return only valid JSON. "
                    "Create campaigns that are usable for a real client, aligned to brand, audience, offer, "
                    "and channel goals."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(payload),
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "campaign_bootstrap",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "campaigns": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "name": {"type": "string"},
                                    "objective": {"type": "string"},
                                    "audience_segment": {"type": "string"},
                                    "offer": {
                                        "anyOf": [
                                            {"type": "string"},
                                            {"type": "null"},
                                        ]
                                    },
                                    "tone_override": {
                                        "anyOf": [
                                            {"type": "string"},
                                            {"type": "null"},
                                        ]
                                    },
                                    "posting_goal": {
                                        "anyOf": [
                                            {"type": "string"},
                                            {"type": "null"},
                                        ]
                                    },
                                    "description": {
                                        "anyOf": [
                                            {"type": "string"},
                                            {"type": "null"},
                                        ]
                                    },
                                },
                                "required": [
                                    "name",
                                    "objective",
                                    "audience_segment",
                                    "offer",
                                    "tone_override",
                                    "posting_goal",
                                    "description",
                                ],
                            },
                        }
                    },
                    "required": ["campaigns"],
                },
                "strict": True,
            }
        },
    )

    return json.loads(response.output_text)
