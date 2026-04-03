from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.pg_tables import ClientPromptProfile


def _normalize_scope_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _profile_matches_scope(
    profile: ClientPromptProfile,
    provider: Optional[str],
    workflow: Optional[str],
    channel: Optional[str],
    content_type: Optional[str],
) -> bool:
    if profile.provider and profile.provider != provider:
        return False
    if profile.workflow and profile.workflow != workflow:
        return False
    if profile.channel and profile.channel != channel:
        return False
    if profile.content_type and profile.content_type != content_type:
        return False
    return True


def _scope_score(
    profile: ClientPromptProfile,
    provider: Optional[str],
    workflow: Optional[str],
    channel: Optional[str],
    content_type: Optional[str],
) -> int:
    score = 0

    if profile.is_default:
        score += 1
    if profile.provider and profile.provider == provider:
        score += 8
    if profile.workflow and profile.workflow == workflow:
        score += 6
    if profile.channel and profile.channel == channel:
        score += 4
    if profile.content_type and profile.content_type == content_type:
        score += 2

    return score


def get_active_prompt_profile(
    db: Session,
    client_id: int,
    provider: Optional[str] = None,
    workflow: Optional[str] = None,
    channel: Optional[str] = None,
    content_type: Optional[str] = None,
) -> Optional[ClientPromptProfile]:
    provider = _normalize_scope_value(provider)
    workflow = _normalize_scope_value(workflow)
    channel = _normalize_scope_value(channel)
    content_type = _normalize_scope_value(content_type)

    profiles = (
        db.query(ClientPromptProfile)
        .filter(
            ClientPromptProfile.client_id == client_id,
            ClientPromptProfile.is_active.is_(True),
        )
        .all()
    )

    best_profile = None
    best_score = -1

    for profile in profiles:
        if not _profile_matches_scope(profile, provider, workflow, channel, content_type):
            continue

        score = _scope_score(profile, provider, workflow, channel, content_type)
        if score > best_score:
            best_score = score
            best_profile = profile

    return best_profile


def serialize_prompt_profile(profile: Optional[ClientPromptProfile]) -> Dict[str, Any]:
    if not profile:
        return {
            "profile_id": None,
            "profile_name": None,
            "brand_voice": "",
            "style_rules": "",
            "negative_prompt": "",
            "creative_guidelines": "",
            "cta_guidelines": "",
            "profile_variables": {},
            "metadata_json": {},
        }

    return {
        "profile_id": profile.id,
        "profile_name": profile.profile_name,
        "brand_voice": profile.brand_voice or "",
        "style_rules": profile.style_rules or "",
        "negative_prompt": profile.negative_prompt or "",
        "creative_guidelines": profile.creative_guidelines or "",
        "cta_guidelines": profile.cta_guidelines or "",
        "profile_variables": profile.profile_variables or {},
        "metadata_json": profile.metadata_json or {},
    }
