from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.pg_tables import PromptTemplate


class SafeFormatDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _normalize_scope_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _scope_score(
    template: PromptTemplate,
    provider: Optional[str],
    workflow: Optional[str],
    channel: Optional[str],
    content_type: Optional[str],
) -> int:
    score = 0

    if template.provider and template.provider == provider:
        score += 8
    if template.workflow and template.workflow == workflow:
        score += 6
    if template.channel and template.channel == channel:
        score += 4
    if template.content_type and template.content_type == content_type:
        score += 2

    return score


def _template_matches_scope(
    template: PromptTemplate,
    provider: Optional[str],
    workflow: Optional[str],
    channel: Optional[str],
    content_type: Optional[str],
) -> bool:
    if template.provider and template.provider != provider:
        return False
    if template.workflow and template.workflow != workflow:
        return False
    if template.channel and template.channel != channel:
        return False
    if template.content_type and template.content_type != content_type:
        return False
    return True


def get_best_prompt_template(
    db: Session,
    template_key: str,
    provider: Optional[str] = None,
    workflow: Optional[str] = None,
    channel: Optional[str] = None,
    content_type: Optional[str] = None,
) -> Optional[PromptTemplate]:
    provider = _normalize_scope_value(provider)
    workflow = _normalize_scope_value(workflow)
    channel = _normalize_scope_value(channel)
    content_type = _normalize_scope_value(content_type)

    candidates = (
        db.query(PromptTemplate)
        .filter(
            PromptTemplate.template_key == template_key,
            PromptTemplate.is_active.is_(True),
        )
        .order_by(desc(PromptTemplate.version), desc(PromptTemplate.id))
        .all()
    )

    best_template = None
    best_score = -1

    for template in candidates:
        if not _template_matches_scope(template, provider, workflow, channel, content_type):
            continue

        score = _scope_score(template, provider, workflow, channel, content_type)
        if score > best_score:
            best_score = score
            best_template = template

    return best_template


def render_prompt_text(template_text: Optional[str], context: Dict[str, Any]) -> str:
    if not template_text:
        return ""
    return template_text.format_map(SafeFormatDict(context))


def render_prompt_template(
    template: Optional[PromptTemplate],
    context: Dict[str, Any],
) -> Dict[str, Any]:
    if not template:
        return {
            "template_id": None,
            "template_key": None,
            "system_prompt": "",
            "user_prompt": "",
            "default_variables": {},
            "metadata_json": {},
        }

    default_variables = template.default_variables or {}
    merged_context = {**default_variables, **context}

    return {
        "template_id": template.id,
        "template_key": template.template_key,
        "system_prompt": render_prompt_text(template.system_prompt, merged_context),
        "user_prompt": render_prompt_text(template.user_prompt_template, merged_context),
        "default_variables": default_variables,
        "metadata_json": template.metadata_json or {},
    }
