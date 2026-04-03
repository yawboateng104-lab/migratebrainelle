from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.integrations.openai_client import generate_structured_creative_spec
from app.services.analytics_signal_service import get_active_feedback_signals
from app.services.creative_request_service import (
    create_resolved_spec,
    get_creative_media_inputs,
    get_creative_request,
)
from app.services.prompt_profile_service import (
    get_active_prompt_profile,
    serialize_prompt_profile,
)
from app.services.prompt_template_service import (
    get_best_prompt_template,
    render_prompt_template,
)
from app.services.provider_routing_service import choose_provider


SUPPORTED_PROMPT_RESOLUTION_MODES = {
    "full_openai",
    "light_openai",
    "no_openai",
}


def _safe_get(obj: Any, field_name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    return getattr(obj, field_name, default)


def _to_dict(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, dict):
        return {key: _to_dict(item) for key, item in value.items()}

    if isinstance(value, list):
        return [_to_dict(item) for item in value]

    if isinstance(value, tuple):
        return [_to_dict(item) for item in value]

    if hasattr(value, "__dict__"):
        result = {}
        for key, item in vars(value).items():
            if key.startswith("_"):
                continue
            result[key] = _to_dict(item)
        return result

    return value


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)

    for key, value in (override or {}).items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _detect_channel(creative_request: Any) -> str:
    request_source = _normalize_text(_safe_get(creative_request, "request_source")).lower()

    if "telegram" in request_source:
        return "telegram"

    if "director" in request_source:
        return "director"

    if "edit" in request_source:
        return "edit"

    return "api"


def _has_source_image(media_inputs: list[Any]) -> bool:
    for media in media_inputs or []:
        media_role = _normalize_text(_safe_get(media, "media_role")).lower()
        storage_key = _safe_get(media, "storage_key")
        media_url = _safe_get(media, "media_url")
        is_primary = bool(_safe_get(media, "is_primary", False))

        if media_role in {"source_image", "reference_image", "image"}:
            if storage_key or media_url:
                return True

        if is_primary and ((storage_key or media_url) and media_role not in {"audio", "voiceover"}):
            return True

    return False


def _needs_voiceover(creative_request: Any, runtime_overrides: Dict[str, Any]) -> bool:
    generation_mode = _normalize_text(_safe_get(creative_request, "generation_mode")).lower()
    raw_input_json = _safe_get(creative_request, "raw_input_json") or {}
    edit_request = runtime_overrides.get("edit_request") or {}

    if generation_mode == "voiceover_video":
        return True

    if isinstance(raw_input_json, dict) and raw_input_json.get("voiceover_required") is True:
        return True

    if isinstance(edit_request, dict) and edit_request.get("keep_voiceover") is True:
        return True

    return False


def _extract_runtime_overrides(creative_request: Any) -> Dict[str, Any]:
    raw_input_json = _safe_get(creative_request, "raw_input_json") or {}

    if not isinstance(raw_input_json, dict):
        raw_input_json = {}

    telegram_generation_context = raw_input_json.get("telegram_generation_context") or {}
    edit_request = raw_input_json.get("edit_request") or {}
    runtime_prompt_overrides = raw_input_json.get("runtime_prompt_overrides") or {}
    director_context = raw_input_json.get("director_context") or {}
    onboarding_context = raw_input_json.get("onboarding_context") or {}
    prompt_resolution_mode = raw_input_json.get("prompt_resolution_mode")

    result: Dict[str, Any] = {
        "telegram_generation_context": telegram_generation_context,
        "edit_request": edit_request,
        "runtime_prompt_overrides": runtime_prompt_overrides,
        "director_context": director_context,
        "onboarding_context": onboarding_context,
        "direct_prompt_mode": bool(raw_input_json.get("direct_prompt_mode")),
        "direct_client_prompt": raw_input_json.get("direct_client_prompt"),
        "client_template_name": raw_input_json.get("client_template_name"),
        "prompt_input_source": raw_input_json.get("prompt_input_source"),
        "provider_locked": bool(raw_input_json.get("provider_locked")),
        "workflow_locked": bool(raw_input_json.get("workflow_locked")),
        "reduce_openai_creative_interpretation": bool(
            raw_input_json.get("reduce_openai_creative_interpretation")
        ),
        "prompt_resolution_mode": prompt_resolution_mode,
    }

    if isinstance(edit_request, dict):
        result["edit_notes"] = edit_request.get("edit_notes")
        result["change_hook"] = edit_request.get("change_hook")
        result["change_cta"] = edit_request.get("change_cta")
        result["change_tone"] = edit_request.get("change_tone")
        result["change_visual_style"] = edit_request.get("change_visual_style")
        result["change_environment_style"] = edit_request.get("change_environment_style")
        result["change_lighting_style"] = edit_request.get("change_lighting_style")
        result["change_camera_style"] = edit_request.get("change_camera_style")
        result["change_motion_intensity"] = edit_request.get("change_motion_intensity")
        result["music_mode"] = edit_request.get("music_mode")
        result["music_mood"] = edit_request.get("music_mood")
        result["music_notes"] = edit_request.get("music_notes")
        result["shot_updates"] = edit_request.get("shot_updates") or []
        result["original_resolved_spec"] = edit_request.get("original_resolved_spec") or {}

    return result


def _determine_prompt_resolution_mode(
    creative_request: Any,
    runtime_overrides: Dict[str, Any],
) -> str:
    explicit_mode = _normalize_text(runtime_overrides.get("prompt_resolution_mode")).lower()

    if explicit_mode in SUPPORTED_PROMPT_RESOLUTION_MODES:
        return explicit_mode

    direct_prompt_mode = bool(runtime_overrides.get("direct_prompt_mode"))
    reduce_openai = bool(runtime_overrides.get("reduce_openai_creative_interpretation"))

    if direct_prompt_mode and reduce_openai:
        return "light_openai"

    return "full_openai"


def _extract_provider_resolution(
    creative_request: Any,
    media_inputs: list[Any],
    runtime_overrides: Dict[str, Any],
) -> Dict[str, Optional[str]]:
    generation_mode = _safe_get(creative_request, "generation_mode")
    preferred_workflow = _safe_get(creative_request, "preferred_workflow")
    has_source_image = _has_source_image(media_inputs)
    needs_voiceover = _needs_voiceover(creative_request, runtime_overrides)

    chosen = choose_provider(
        generation_mode=generation_mode,
        has_source_image=has_source_image,
        needs_voiceover=needs_voiceover,
        preferred_workflow=preferred_workflow,
    )

    channel = _detect_channel(creative_request)
    content_type = _safe_get(creative_request, "content_type") or "video"

    return {
        "provider": chosen.get("provider"),
        "workflow": chosen.get("workflow"),
        "channel": channel,
        "content_type": content_type,
        "generation_mode": generation_mode,
        "has_source_image": has_source_image,
        "needs_voiceover": needs_voiceover,
    }


def _extract_template_key(
    creative_request: Any,
    provider_context: Dict[str, Optional[str]],
) -> str:
    raw_input_json = _safe_get(creative_request, "raw_input_json") or {}
    explicit_template_key = None

    if isinstance(raw_input_json, dict):
        explicit_template_key = raw_input_json.get("prompt_template_key")

    if explicit_template_key:
        return str(explicit_template_key)

    workflow = provider_context.get("workflow")
    content_type = provider_context.get("content_type")
    target_platform = _safe_get(creative_request, "target_platform")

    if workflow and content_type:
        return f"{workflow}_{content_type}"

    if target_platform and content_type:
        return f"{target_platform}_{content_type}"

    if workflow:
        return workflow

    if content_type:
        return f"default_{content_type}"

    return "default_video"


def _build_prompt_context(
    creative_request: Any,
    media_inputs: list[Any],
    feedback_signals: list[Any],
    profile_payload: Dict[str, Any],
    provider_context: Dict[str, Any],
    runtime_overrides: Dict[str, Any],
    prompt_resolution_mode: str,
) -> Dict[str, Any]:
    creative_request_dict = _to_dict(creative_request) or {}
    media_inputs_dict = _to_dict(media_inputs) or []
    feedback_signals_dict = _to_dict(feedback_signals) or []
    profile_variables = profile_payload.get("profile_variables") or {}

    base_context = {
        "provider": provider_context.get("provider") or "",
        "workflow": provider_context.get("workflow") or "",
        "channel": provider_context.get("channel") or "",
        "content_type": provider_context.get("content_type") or "",
        "generation_mode": provider_context.get("generation_mode") or "",
        "has_source_image": provider_context.get("has_source_image"),
        "needs_voiceover": provider_context.get("needs_voiceover"),
        "prompt_resolution_mode": prompt_resolution_mode,
        "creative_request": creative_request_dict,
        "media_inputs": media_inputs_dict,
        "feedback_signals": feedback_signals_dict,
        "brand_voice": profile_payload.get("brand_voice") or "",
        "style_rules": profile_payload.get("style_rules") or "",
        "negative_prompt": profile_payload.get("negative_prompt") or "",
        "creative_guidelines": profile_payload.get("creative_guidelines") or "",
        "cta_guidelines": profile_payload.get("cta_guidelines") or "",
        "edit_request": runtime_overrides.get("edit_request") or {},
        "edit_notes": runtime_overrides.get("edit_notes") or "",
        "change_hook": runtime_overrides.get("change_hook") or "",
        "change_cta": runtime_overrides.get("change_cta") or "",
        "change_tone": runtime_overrides.get("change_tone") or "",
        "change_visual_style": runtime_overrides.get("change_visual_style") or "",
        "change_environment_style": runtime_overrides.get("change_environment_style") or "",
        "change_lighting_style": runtime_overrides.get("change_lighting_style") or "",
        "change_camera_style": runtime_overrides.get("change_camera_style") or "",
        "change_motion_intensity": runtime_overrides.get("change_motion_intensity") or "",
        "music_mode": runtime_overrides.get("music_mode") or "",
        "music_mood": runtime_overrides.get("music_mood") or "",
        "music_notes": runtime_overrides.get("music_notes") or "",
        "shot_updates": runtime_overrides.get("shot_updates") or [],
        "original_resolved_spec": runtime_overrides.get("original_resolved_spec") or {},
        "telegram_generation_context": runtime_overrides.get("telegram_generation_context") or {},
        "director_context": runtime_overrides.get("director_context") or {},
        "onboarding_context": runtime_overrides.get("onboarding_context") or {},
        "runtime_prompt_overrides": runtime_overrides.get("runtime_prompt_overrides") or {},
        "direct_prompt_mode": runtime_overrides.get("direct_prompt_mode"),
        "direct_client_prompt": runtime_overrides.get("direct_client_prompt") or "",
        "client_template_name": runtime_overrides.get("client_template_name") or "",
        "prompt_input_source": runtime_overrides.get("prompt_input_source") or "",
        "provider_locked": runtime_overrides.get("provider_locked"),
        "workflow_locked": runtime_overrides.get("workflow_locked"),
        "reduce_openai_creative_interpretation": runtime_overrides.get(
            "reduce_openai_creative_interpretation"
        ),
    }

    merged = _deep_merge(base_context, profile_variables)

    if isinstance(runtime_overrides.get("runtime_prompt_overrides"), dict):
        merged = _deep_merge(merged, runtime_overrides["runtime_prompt_overrides"])

    return merged


def _serialize_feedback_signals_for_prompt(feedback_signals: list[Any]) -> list[dict]:
    serialized = []

    for signal in feedback_signals or []:
        serialized.append(
            {
                "signal_source": _safe_get(signal, "signal_source"),
                "signal_type": _safe_get(signal, "signal_type"),
                "title": _safe_get(signal, "title"),
                "summary": _safe_get(signal, "summary"),
                "recommendation": _safe_get(signal, "recommendation"),
                "priority_score": _safe_get(signal, "priority_score"),
                "structured_signal_json": _to_dict(_safe_get(signal, "structured_signal_json")),
            }
        )

    return serialized


def _build_openai_payload(
    creative_request: Any,
    media_inputs: list[Any],
    feedback_signals: list[Any],
    provider_context: Dict[str, Any],
    template_render: Dict[str, Any],
    profile_payload: Dict[str, Any],
    runtime_overrides: Dict[str, Any],
    prompt_resolution_mode: str,
) -> Dict[str, Any]:
    creative_request_dict = _to_dict(creative_request) or {}
    media_inputs_dict = _to_dict(media_inputs) or []
    raw_input_json = _safe_get(creative_request, "raw_input_json") or {}

    return {
        "resolution_version": "v3_prompt_orchestration",
        "prompt_resolution_mode": prompt_resolution_mode,
        "provider_context": _to_dict(provider_context),
        "creative_request": creative_request_dict,
        "media_inputs": media_inputs_dict,
        "feedback_signals": _serialize_feedback_signals_for_prompt(feedback_signals),
        "prompt_template": _to_dict(template_render),
        "client_prompt_profile": _to_dict(profile_payload),
        "runtime_overrides": _to_dict(runtime_overrides),
        "raw_input_json": _to_dict(raw_input_json) if isinstance(raw_input_json, dict) else {},
        "instructions": {
            "selected_provider": provider_context.get("provider"),
            "selected_workflow": provider_context.get("workflow"),
            "selected_generation_mode": provider_context.get("generation_mode"),
            "target_platform": _safe_get(creative_request, "target_platform"),
            "content_type": _safe_get(creative_request, "content_type"),
            "channel": provider_context.get("channel"),
            "has_source_image": provider_context.get("has_source_image"),
            "needs_voiceover": provider_context.get("needs_voiceover"),
            "prompt_resolution_mode": prompt_resolution_mode,
            "use_template_system_prompt": template_render.get("system_prompt") or "",
            "use_template_user_prompt": template_render.get("user_prompt") or "",
            "brand_voice": profile_payload.get("brand_voice") or "",
            "style_rules": profile_payload.get("style_rules") or "",
            "negative_prompt_from_profile": profile_payload.get("negative_prompt") or "",
            "creative_guidelines": profile_payload.get("creative_guidelines") or "",
            "cta_guidelines": profile_payload.get("cta_guidelines") or "",
            "edit_notes": runtime_overrides.get("edit_notes") or "",
            "shot_updates": runtime_overrides.get("shot_updates") or [],
            "music_notes": runtime_overrides.get("music_notes") or "",
            "direct_prompt_mode": runtime_overrides.get("direct_prompt_mode"),
            "direct_client_prompt": runtime_overrides.get("direct_client_prompt") or "",
            "client_template_name": runtime_overrides.get("client_template_name") or "",
            "prompt_input_source": runtime_overrides.get("prompt_input_source") or "",
            "provider_locked": runtime_overrides.get("provider_locked"),
            "workflow_locked": runtime_overrides.get("workflow_locked"),
            "reduce_openai_creative_interpretation": runtime_overrides.get(
                "reduce_openai_creative_interpretation"
            ),
            "light_openai_mode_rules": (
                "If prompt_resolution_mode is light_openai, preserve the direct client prompt as the main prompt. "
                "Only do minimal structuring, cleanup, and provider payload preparation. "
                "Do not invent a new concept."
            ),
            "full_openai_mode_rules": (
                "If prompt_resolution_mode is full_openai, you may fully synthesize the creative concept using "
                "template, profile, analytics, and request data."
            ),
        },
    }


def _build_provider_payload_defaults(
    creative_request: Any,
    provider_context: Dict[str, Any],
    runtime_overrides: Dict[str, Any],
) -> Dict[str, Any]:
    raw_input_json = _safe_get(creative_request, "raw_input_json") or {}
    runtime_prompt_overrides = runtime_overrides.get("runtime_prompt_overrides") or {}
    edit_request = runtime_overrides.get("edit_request") or {}

    target_platform = _safe_get(creative_request, "target_platform") or "instagram"
    target_aspect_ratio = "9:16"

    preserve_environment = True
    preserve_identity = True
    use_source_image_strongly = bool(provider_context.get("has_source_image"))

    if isinstance(raw_input_json, dict):
        preserve_environment = raw_input_json.get("preserve_environment", preserve_environment)
        preserve_identity = raw_input_json.get("preserve_identity", preserve_identity)
        use_source_image_strongly = raw_input_json.get(
            "use_source_image_strongly",
            use_source_image_strongly,
        )

    if isinstance(edit_request, dict):
        preserve_environment = edit_request.get("keep_source_image", preserve_environment)

    if isinstance(runtime_prompt_overrides, dict):
        target_aspect_ratio = runtime_prompt_overrides.get("target_aspect_ratio", target_aspect_ratio)

    return {
        "ratio": target_aspect_ratio,
        "voice_id": None,
        "visual_style_override": runtime_overrides.get("change_visual_style") or None,
        "camera_style": runtime_overrides.get("change_camera_style") or None,
        "motion_intensity": runtime_overrides.get("change_motion_intensity") or None,
        "environment_style": runtime_overrides.get("change_environment_style") or None,
        "lighting_style": runtime_overrides.get("change_lighting_style") or None,
        "preserve_environment": preserve_environment,
        "preserve_identity": preserve_identity,
        "use_source_image_strongly": use_source_image_strongly,
        "shot_prompts": None,
        "platform_rendering_hints": {
            "target_platform": target_platform,
            "target_aspect_ratio": target_aspect_ratio,
            "optimize_for_short_form_hook": True,
            "safe_text_overlay_regions": True,
        },
    }


def _build_no_openai_prompt_text(
    creative_request: Any,
    profile_payload: Dict[str, Any],
    runtime_overrides: Dict[str, Any],
) -> str:
    direct_client_prompt = _normalize_text(runtime_overrides.get("direct_client_prompt"))
    if not direct_client_prompt:
        direct_client_prompt = _normalize_text(_safe_get(creative_request, "scene_description"))

    if not direct_client_prompt:
        direct_client_prompt = _normalize_text(_safe_get(creative_request, "extra_instructions"))

    if not direct_client_prompt:
        direct_client_prompt = _normalize_text(_safe_get(creative_request, "description"))

    style_rules = _normalize_text(profile_payload.get("style_rules"))
    brand_voice = _normalize_text(profile_payload.get("brand_voice"))
    one_time_override = _normalize_text(
        (runtime_overrides.get("runtime_prompt_overrides") or {}).get("telegram_freeform_override")
    )
    edit_notes = _normalize_text(runtime_overrides.get("edit_notes"))

    lines = []

    if direct_client_prompt:
        lines.append(direct_client_prompt)

    if one_time_override:
        lines.append(f"Additional override: {one_time_override}")

    if style_rules:
        lines.append(f"Apply brand style rules: {style_rules}")

    if brand_voice:
        lines.append(f"Maintain brand voice: {brand_voice}")

    if edit_notes:
        lines.append(f"Apply edit instructions: {edit_notes}")

    return "\n".join(line for line in lines if line).strip()


def _build_non_openai_spec(
    creative_request: Any,
    provider_context: Dict[str, Any],
    profile_payload: Dict[str, Any],
    runtime_overrides: Dict[str, Any],
    prompt_resolution_mode: str,
) -> Dict[str, Any]:
    prompt_text = _build_no_openai_prompt_text(
        creative_request=creative_request,
        profile_payload=profile_payload,
        runtime_overrides=runtime_overrides,
    )

    if not prompt_text:
        prompt_text = "Create the requested branded short-form video."

    notes = [
        f"prompt_resolution_mode={prompt_resolution_mode}",
        f"provider={provider_context.get('provider')}",
        f"workflow={provider_context.get('workflow')}",
    ]

    if runtime_overrides.get("client_template_name"):
        notes.append(f"client_template_name={runtime_overrides.get('client_template_name')}")

    if runtime_overrides.get("prompt_input_source"):
        notes.append(f"prompt_input_source={runtime_overrides.get('prompt_input_source')}")

    return {
        "provider": provider_context.get("provider"),
        "workflow": provider_context.get("workflow"),
        "generation_mode": _safe_get(creative_request, "generation_mode") or "image_to_video",
        "prompt_text": prompt_text,
        "negative_prompt": profile_payload.get("negative_prompt") or None,
        "voiceover_script": None,
        "caption_text": None,
        "hashtags": None,
        "provider_payload_json": _build_provider_payload_defaults(
            creative_request=creative_request,
            provider_context=provider_context,
            runtime_overrides=runtime_overrides,
        ),
        "resolution_notes": " | ".join(notes),
    }


def _finalize_structured_spec(
    structured_spec: Dict[str, Any],
    creative_request: Any,
    provider_context: Dict[str, Any],
    profile_payload: Dict[str, Any],
    template_render: Dict[str, Any],
    runtime_overrides: Dict[str, Any],
    prompt_resolution_mode: str,
) -> Dict[str, Any]:
    spec = dict(structured_spec or {})

    if not spec.get("provider"):
        spec["provider"] = provider_context.get("provider")

    if not spec.get("workflow"):
        spec["workflow"] = provider_context.get("workflow")

    if not spec.get("generation_mode"):
        spec["generation_mode"] = (
            _safe_get(creative_request, "generation_mode")
            or provider_context.get("generation_mode")
            or "image_to_video"
        )

    spec.setdefault("prompt_text", template_render.get("user_prompt") or "")
    spec.setdefault("negative_prompt", profile_payload.get("negative_prompt") or None)
    spec.setdefault("voiceover_script", None)
    spec.setdefault("caption_text", None)
    spec.setdefault("hashtags", None)
    spec.setdefault("provider_payload_json", None)
    spec.setdefault("resolution_notes", None)

    resolution_notes = spec.get("resolution_notes") or ""
    notes = []

    if resolution_notes:
        notes.append(str(resolution_notes).strip())

    notes.append(f"prompt_resolution_mode={prompt_resolution_mode}")

    if template_render.get("template_key"):
        notes.append(f"template_key={template_render['template_key']}")

    if profile_payload.get("profile_name"):
        notes.append(f"profile_name={profile_payload['profile_name']}")

    if runtime_overrides.get("edit_notes"):
        notes.append("edit_revision_applied=true")

    if runtime_overrides.get("direct_prompt_mode"):
        notes.append("direct_prompt_mode=true")

    spec["resolution_notes"] = " | ".join(note for note in notes if note) or None

    return spec


def resolve_creative_request(db: Session, creative_request_id: int):
    creative_request = get_creative_request(db, creative_request_id)
    if not creative_request:
        raise ValueError("Creative request not found")

    media_inputs = get_creative_media_inputs(db, creative_request_id)
    feedback_signals = get_active_feedback_signals(db, creative_request.client_id)
    runtime_overrides = _extract_runtime_overrides(creative_request)

    provider_context = _extract_provider_resolution(
        creative_request=creative_request,
        media_inputs=media_inputs,
        runtime_overrides=runtime_overrides,
    )

    prompt_resolution_mode = _determine_prompt_resolution_mode(
        creative_request=creative_request,
        runtime_overrides=runtime_overrides,
    )

    template_key = _extract_template_key(
        creative_request=creative_request,
        provider_context=provider_context,
    )

    prompt_template = get_best_prompt_template(
        db=db,
        template_key=template_key,
        provider=provider_context.get("provider"),
        workflow=provider_context.get("workflow"),
        channel=provider_context.get("channel"),
        content_type=provider_context.get("content_type"),
    )

    prompt_profile = get_active_prompt_profile(
        db=db,
        client_id=creative_request.client_id,
        provider=provider_context.get("provider"),
        workflow=provider_context.get("workflow"),
        channel=provider_context.get("channel"),
        content_type=provider_context.get("content_type"),
    )

    profile_payload = serialize_prompt_profile(prompt_profile)

    prompt_context = _build_prompt_context(
        creative_request=creative_request,
        media_inputs=media_inputs,
        feedback_signals=feedback_signals,
        profile_payload=profile_payload,
        provider_context=provider_context,
        runtime_overrides=runtime_overrides,
        prompt_resolution_mode=prompt_resolution_mode,
    )

    template_render = render_prompt_template(
        template=prompt_template,
        context=prompt_context,
    )

    if prompt_resolution_mode == "no_openai":
        finalized_spec = _build_non_openai_spec(
            creative_request=creative_request,
            provider_context=provider_context,
            profile_payload=profile_payload,
            runtime_overrides=runtime_overrides,
            prompt_resolution_mode=prompt_resolution_mode,
        )
    else:
        openai_payload = _build_openai_payload(
            creative_request=creative_request,
            media_inputs=media_inputs,
            feedback_signals=feedback_signals,
            provider_context=provider_context,
            template_render=template_render,
            profile_payload=profile_payload,
            runtime_overrides=runtime_overrides,
            prompt_resolution_mode=prompt_resolution_mode,
        )

        structured_spec = generate_structured_creative_spec(openai_payload)

        finalized_spec = _finalize_structured_spec(
            structured_spec=structured_spec,
            creative_request=creative_request,
            provider_context=provider_context,
            profile_payload=profile_payload,
            template_render=template_render,
            runtime_overrides=runtime_overrides,
            prompt_resolution_mode=prompt_resolution_mode,
        )

    return create_resolved_spec(
        db=db,
        creative_request_id=creative_request_id,
        client_id=creative_request.client_id,
        spec=finalized_spec,
    )
